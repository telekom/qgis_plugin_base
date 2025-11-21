# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import Dict, List, Tuple, Union, Optional

from qgis.core import (QgsGeometry, QgsPointXY, QgsFeatureIterator, QgsFeature, QgsWkbTypes,
                       QgsSpatialIndex, QgsRectangle)
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .geometry import get_polyline
from .geometry_sort_line import get_neighbor_type
from .. import constants


class GroupMergableLineFeatures(QObject):
    """ Small helper class with the option to a progressbar to get mergable line features.

        :param features: List of QgsFeatures to group by their coordinates
        :param epsilon: Epsilon/Tolerance for some coordinate precisions
    """

    # pyqtSignal(current step, max steps, text)
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")

    def __init__(self, features: Union[List[QgsFeature], QgsFeatureIterator],
                 epsilon: float = constants.EPSILON,
                 parent: Optional[QObject]=None):

        super().__init__(parent)

        if not isinstance(features, list):
            # convert a tuple to a list, fetch all features from the iterator
            features = list(features)

        # internal attributes
        self.__features: List[QgsFeature] = features
        self.__epsilon = epsilon
        # mapping of possible new poly line for the mergable feature id (fid)
        # poly lines may be duplicate in the dictionary in case of mergable features
        self.fid_to_possible_poly_line: Dict[int, List[QgsPointXY]] = {}
        self.fid_to_possible_poly_line = {}

    @staticmethod
    def __get_polyline(feature: QgsFeature) -> List[QgsFeature]:
        geometry = feature.geometry()
        if geometry.type() != QgsWkbTypes.LineGeometry:
            geometry_type_name = QgsWkbTypes.geometryDisplayString(geometry.type())
            raise ValueError(f"Given geometry type of feature (id={feature.id()}) is not a LineGeometry, "
                             f"got '{geometry_type_name}'")

        poly_line = get_polyline(geometry)
        return poly_line

    def run(self) -> List[List[QgsFeature]]:
        """ Sorts a list of QgsFeature (geometry = LineString) by given line end points.
            Not connected features will be sorted in a separate feature list.
        """
        # internal mappings
        feature_list = [(f.id(), self.__get_polyline(f), f) for f in self.__features]
        feature_dict = {fid: f for fid, _, f in feature_list}
        all_feature_dict = {fid: (fid, poly_line, feature) for (fid, poly_line, feature) in feature_list}

        # create the spatial index for the features to be checked
        # uses a spatial index to prevent looping over all features again and again
        spatial = QgsSpatialIndex(flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        spatial.addFeatures(self.__features)

        max_progress = len(self.__features)

        # helper to pop the first key and value from the features to check
        lambda_pop = lambda: all_feature_dict.pop(list(all_feature_dict.keys())[0])

        # init values with the first feature to pop from the main dictionary
        all_sorted_geometries: List[List[Tuple[int, List[QgsPointXY], QgsFeature]]] = [[lambda_pop()]]
        current_sorting_list = all_sorted_geometries[-1]
        # remove from the spatial index
        spatial.deleteFeature(current_sorting_list[0][2])
        current_poly_line = current_sorting_list[0][1].copy()

        while all_feature_dict:

            self.progressChanged.emit(max_progress - len(all_feature_dict), max_progress, "")

            found = False

            # get bbox form the first and last sorted vertices
            bbox_1 = QgsRectangle.fromCenterAndSize(current_poly_line[0], self.__epsilon, self.__epsilon)
            bbox_2 = QgsRectangle.fromCenterAndSize(current_poly_line[-1], self.__epsilon, self.__epsilon)

            # get the intersecting features based on the bbox and the stored geometries (flag)
            # distance does not matter here
            fids = set(spatial.intersects(bbox_1)) | set(spatial.intersects(bbox_2))

            for i, element in enumerate(map(lambda fid_: all_feature_dict[fid_], fids)):
                # unpack the current intersecting feature data
                fid, poly_line, _ = element
                feature_to_check = feature_dict[fid]

                if (first_n_type := get_neighbor_type(current_poly_line, poly_line, self.__epsilon)) == constants.N_LEFT:
                    current_sorting_list.insert(0, all_feature_dict.pop(fid))
                    spatial.deleteFeature(feature_to_check)
                    current_poly_line = poly_line + current_poly_line[1:]
                    found = True
                    break

                if (last_n_type := get_neighbor_type(current_poly_line, poly_line, self.__epsilon)) == constants.N_RIGHT:
                    current_sorting_list.append(all_feature_dict.pop(fid))
                    spatial.deleteFeature(feature_to_check)
                    current_poly_line.extend(poly_line[1:])
                    found = True
                    break

                if first_n_type == constants.N_LEFT_REVERSED:
                    # poly line must be reversed
                    poly_line.reverse()
                    # update the QgsFeature's geometry
                    feature_to_check.setGeometry(QgsGeometry.fromPolylineXY(poly_line))
                    current_sorting_list.insert(0, all_feature_dict.pop(fid))
                    spatial.deleteFeature(feature_to_check)
                    current_poly_line = poly_line + current_poly_line[1:]
                    found = True
                    break

                if last_n_type == constants.N_RIGHT_REVERSED:
                    # poly line must be reversed
                    poly_line.reverse()
                    # update the QgsFeature's geometry
                    feature_to_check.setGeometry(QgsGeometry.fromPolylineXY(poly_line))
                    current_sorting_list.append(all_feature_dict.pop(fid))
                    current_poly_line.extend(poly_line[1:])
                    spatial.deleteFeature(feature_to_check)
                    found = True
                    break

            if not found:
                # save the current values on self
                self.fid_to_possible_poly_line.update({
                    fid: current_poly_line
                    for (fid, *_) in current_sorting_list
                })

                # start the next iteration
                all_sorted_geometries.append([lambda_pop()])
                current_sorting_list = all_sorted_geometries[-1]
                current_poly_line = current_sorting_list[0][1].copy()
                spatial.deleteFeature(current_sorting_list[0][2])

        # save the (last) current values on self
        self.fid_to_possible_poly_line.update({
            fid: current_poly_line
            for (fid, *_) in current_sorting_list
        })

        # create the sorted feature list
        sorted_features = [[feature_dict[fid] for fid, *_ in sorted_list]
                            for sorted_list in all_sorted_geometries]

        return sorted_features
