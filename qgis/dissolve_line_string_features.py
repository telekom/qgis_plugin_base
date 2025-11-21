# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, List, Optional

from qgis.core import QgsVectorLayer, QgsFeature, QgsFeatureRequest, QgsFields, QgsPointXY
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .mergable_line_features import GroupMergableLineFeatures
from .spatial_line_ends_to_point_v2 import LineEndsToPointSpatialIndexV2
from ..constants import TO_STRING_PREC


class DissolveLineStringFeatures(QObject):
    """ Small dissolve algorithm to group dissolvable features by its attributes and geometry.
        Only for features and its geometry type of LineString (single type geometry).

        .. code-block:: python

            dissolver = DissolveLineStringFeatures(...)
            dissolver.init()  # init before run
            dissolver.run()  # run after init

        :param features: List of QgsFeatures. All provided QgsFeature's attribute names will be used.
                         If no attribute names (fields) provided, the dissolve will run only with the geometries.
        :param ignore_attribute_names: A list of attribute names to ignore during the feature attribute comparison while the grouping.
                                       E.g. if the feature is coming from a GeoPackage vector layer you can add "fid" here to keep transparency.
        :param cut_at_multiple_connection_points: Regroup grouped features at points with more than two line connections.
    """

    # pyqtSignal(current step, max steps, text)
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")
    # pyqtSignal(current step, max steps, text)
    subProgressChanged = pyqtSignal(int, int, str, name="subProgressChanged")


    def __init__(self, features: List[QgsFeature],
                 ignore_attribute_names: Optional[List[str]] = None,
                 cut_at_multiple_connection_points: bool = False,
                 parent: Optional[QObject]=None):

        super().__init__(parent)

        # internal attributes
        self.__features: List[QgsFeature] = features
        self.__ignore_attribute_names: List[str] = ignore_attribute_names or []
        self.__cut_at_multiple_connection_points: bool = cut_at_multiple_connection_points
        # mapping of possible new poly line for the mergable feature id (fid)
        # poly lines may be duplicate in the dictionary in case of mergable features
        self.fid_to_possible_poly_line: Dict[int, List[QgsPointXY]] = {}

        # will be updated later
        self.__init_called: bool = False
        self.__spatial: LineEndsToPointSpatialIndexV2 = LineEndsToPointSpatialIndexV2([0, -1],
                                                                                      LineEndsToPointSpatialIndexV2.PER_SEGMENT)
        self.__attribute_names: List[str] = []  # ignore_attribute_names values are not in this list
        self.__grouped_features_by_attributes: List[List[QgsFeature]] = []  # pre-processing of mergable features
        self.__grouped_features_by_geometries: List[List[QgsFeature]] = []  # needs a filled __grouped_features_by_attributes list

    def init(self):
        """ Init some values. No progress emitted here. """

        if self.__init_called:
            raise RuntimeError("init can only be called once per object instance")

        if not self.__features:
            self.__init_called: bool = True
            return

        # init the line spatial
        self.__spatial.init(self.__features)

        # validates the feature attribute names to be overall equal
        set_attribute_names = set(self.__features[0].fields().names())
        if not all(map(lambda feature: set(feature.fields().names()) == set_attribute_names, self.__features)):
            raise ValueError("Provided feature list is incompatible. Not all features have the same attribute names.")
        self.__attribute_names: List[str] = [name for name in self.__features[0].fields().names()
                                             if name not in self.__ignore_attribute_names]

        self.__init_called = True

    def run(self) -> List[List[QgsFeature]]:
        """ Runs the algorithm and returns a list of grouped and mergable features.
            Non-mergable features are not included in the returned list.
        """

        if not self.__init_called:
            raise RuntimeError("init not called")

        # group the features by the available attribute names
        self.progressChanged.emit(1, 2, "Gruppiere Objekte nach verfügbaren Attributen")
        self.__group_features_by_attributes()

        # group the features by the available attribute names
        self.progressChanged.emit(2, 2, "Gruppiere Objekte nach Geometrien")
        self.__group_features_by_geometries()

        return self.__grouped_features_by_geometries

    def __group_features_by_attributes(self):
        """ Group all features by its attributes.
        """

        # copy the feature list to a shallow list
        features = self.__features.copy()
        max_progress = len(self.__features)

        while features:

            # pop the last feature to reduce the list size
            main_feature = features.pop()
            self.__grouped_features_by_attributes.append([main_feature])
            grouped_features = self.__grouped_features_by_attributes[-1]

            self.subProgressChanged.emit(max_progress - len(features), max_progress, "")

            for other_feature in filter(lambda f: self.__compare_feature_attributes(main_feature, f),
                                        features.copy()):
                # attributes are equal, remove from the feature list
                features.remove(other_feature)
                # add the feature to the grouped list
                grouped_features.append(other_feature)

                self.subProgressChanged.emit(max_progress - len(features), max_progress, "")

    def __group_features_by_geometries(self):
        """ Group all pre-grouped features now by the geometries.
        """

        # all elements and its element length
        max_loops = len(self.__grouped_features_by_attributes) + sum(map(len, self.__grouped_features_by_attributes))
        current_loop_value = 0

        # read the points from the line spatial index
        if self.__cut_at_multiple_connection_points:
            connection_points = [point_str for point_str, count in self.__spatial.get_mapped_point_counts().items()
                                 if count > 2]
        else:
            connection_points = []

        for i, feature_group in enumerate(self.__grouped_features_by_attributes):

            self.subProgressChanged.emit(current_loop_value, max_loops, "")

            if len(feature_group) < 2:
                # nothing to merge, skip this

                current_loop_value += (1 + len(feature_group))

                continue

            def __sub_progress(current_value: int, max_value: int, message: str):
                self.subProgressChanged.emit(current_loop_value + current_value, max_loops, "")

            # create the grouper instance
            grouper = GroupMergableLineFeatures(feature_group)
            grouper.progressChanged.connect(__sub_progress)

            # run the grouping by the geometries
            result = grouper.run()
            self.fid_to_possible_poly_line.update(grouper.fid_to_possible_poly_line)

            # reduce the feature list to groups with at least two features per group
            groups = [r for r in result if len(r) > 1]

            # regroup the groups in case of points with more than 2 line connections
            if self.__cut_at_multiple_connection_points:
                new_groups = []
                for group in groups:
                    new_groups.extend(self.__split_feature_groups_by_points(group, connection_points))

                # reduce groups to at least groups of one feature per group
                groups = [r for r in new_groups if len(r) > 1]

            # extend the result to the grouped geometries list
            # add only lists with at least 2 elements in it
            self.__grouped_features_by_geometries.extend(groups)

            current_loop_value += (1 + len(feature_group))

        # current_loop_value should be equal to max_loops
        if current_loop_value != max_loops:
            raise ValueError(
                f"Unkown error. "
                f"Progress result unexpected {current_loop_value=} is not equal to {max_loops}")
        self.subProgressChanged.emit(current_loop_value, max_loops, "")

    def __compare_feature_attributes(self, feature_a, feature_b) -> bool:
        """ Return True, if the attributes are equal """

        if not self.__attribute_names:
            # always True
            return True

        return all(map(lambda name: feature_a[name] == feature_b[name], self.__attribute_names))

    def __split_feature_groups_by_points(self, features: List[QgsFeature],
                                         connection_points: List[str]) -> List[List[QgsFeature]]:
        """ Split the already sorted feature list into new lists, when necessary.
            The geometries from features from sorted feature list must be sorted as well.
            The feature geometries must be connected.

            :param features: List of sorted features with connected geometries.
            :param connection_points: list of point string, where to split the sorted feature list
        """

        # new feature group
        new_groups: List[List[QgsFeature]] = [[features[0]]]

        for feature in features[1:]:
            # get the start point from the feature as a string
            poly_line: List[QgsPointXY] = feature.geometry().asPolyline()
            feature_start_point: QgsPointXY = poly_line[0]
            start_point_str = feature_start_point.toString(TO_STRING_PREC)

            # check, if the next feature must be added to a new or an existing group
            if start_point_str in connection_points:
                # add a new feature group
                new_groups.append([feature])
            else:
                # add to existing feature group
                new_groups[-1].append(feature)

        # update the internal possible merged polyline per fid
        for group in new_groups:
            # expecting, that all poly lines set on the features are correct
            possible_poly_line = group[0].geometry().asPolyline()

            for feature in group[1:]:
                # ignore the first vertex, already present as the last from the current list
                possible_poly_line.extend(feature.geometry().asPolyline()[1:])

            self.fid_to_possible_poly_line.update({
                feature.id(): possible_poly_line
                for feature in group
            })

        return new_groups

    @classmethod
    def get_features_from_layer(cls, layer: QgsVectorLayer, request: QgsFeatureRequest):
        return list(layer.getFeatures(request))

    @classmethod
    def get_request_from_attribute_names(cls, attribute_names: List[str], source_fields: QgsFields):
        """ Returns a request object.

            :param attribute_names: Attributes/Fields to fetch
            :param source_fields: QgsFields config with all available fields. E.g.`layer.dataProvider().fields()´
        """
        req = QgsFeatureRequest()
        req = req.setSubsetOfAttributes(attribute_names, source_fields)

        return req
