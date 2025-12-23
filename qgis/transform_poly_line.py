# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.core import (QgsPointXY, QgsVectorLayer, QgsWkbTypes,
                       QgsGeometry, QgsFeatureRequest,
                       QgsFeature, QgsProject)

from typing import List, Optional, Tuple, Dict

from .poly_line_wrapper import PolylineWrapper
from .path_finder import PathFinder
from .geometry_sort_line import sort_lines_features
from .geometry import (get_point, transform_point, get_multi_point, transform_geometry,
                       get_polyline, is_point_on_line, is_point_in_polylist,
                       get_point_index)
from .layer_features import get_feature_ids_containing, get_points_from_help_line
from .layer_edit import add_vertices

from ..exceptions import (NoPathFoundError, PointNotOnPolyLineError,
                          NoIntersectionFoundError, PreparationError,
                          TransformError, RollbackError)
from ..constants import TO_STRING_PREC, EPSILON, N_LEFT, N_RIGHT, EPSILON_METRES


class TransformPolyline:
    """

        :param point_list: point steps (some special here)
                           [
                            # first points have to be equal
                            (old_point, old_point),

                            # inner points can be different, but new_point have to be new_poly_line
                            (old_point, new_point),

                            # last points have to be equal
                            (old_point, old_point),
                           ]
                           This List allows you to define more reference points for one transform task.
                           A poly line path must be findable from first to last point.
        :param new_poly_line: new poly line from start to end without steps
        :param line_layer: main destination line layer for changes
        :param other_layers: other layers, where just to move old vertices to new coordinate,
                             when coordinate is on old calculated line.
                             CRS from these layers have to be equal to main/line layer.
        :param commit: commit changes to data provider on each layer on finish
    """

    def __init__(self, point_list: List[Tuple[QgsPointXY, QgsPointXY]],
                 new_poly_line: List[QgsPointXY],
                 line_layer: QgsVectorLayer,
                 other_layers: Optional[List[QgsVectorLayer]] = None,
                 commit: bool = False):

        if not self.is_layer_compatible(line_layer):
            raise ValueError("layer not compatible")

        # check parameters
        if len(point_list) < 2:
            raise ValueError
        if len(new_poly_line) < 2:
            raise ValueError

        self.other_layers = other_layers if other_layers else []
        self.point_list = point_list
        self.path_data: List[Tuple[List[int], List[QgsPointXY]]] = []
        self.new_poly_line = new_poly_line  # full new poly line

        self.line_layer = line_layer
        self.crs = line_layer.dataProvider().crs()
        self.commit = commit
        self.transform_point_map: Dict[str, QgsPointXY] = {}

        # maybe to rollBack?
        self.source_geometry_map: Dict[QgsVectorLayer, Dict[int, QgsGeometry]] = {
            layer: {} for layer in [self.line_layer] + other_layers
        }

        # edit map, without temporary changes on vector layer
        self.edit_feature_map: Dict[QgsVectorLayer, Dict[int, QgsFeature]] = {
            layer: {} for layer in [self.line_layer] + other_layers
        }

        # def run()
        self.iteration: int = -1  # current run iteration
        self.start_point: Optional[QgsPointXY] = None  # old start point from current iteration
        self.end_point: Optional[QgsPointXY] = None  # old end point from current iteration
        self.new_start_point: Optional[QgsPointXY] = None  # new start point from current iteration
        self.new_end_point: Optional[QgsPointXY] = None  # new end point from current iteration
        self.use_poly_line: List[QgsPointXY] = []  # poly line to use from current iteration
        self.merged_old_line: List[QgsPointXY] = []  # old poly line on sorted features to use from current iteration
        self.sorted_main_features: List[QgsFeature] = []  # sorted features for current iteration

        for layer in self.other_layers:
            if not self.is_layer_compatible(layer):
                raise ValueError(f"{layer} not compatible")

            if layer.dataProvider().crs().authid() != self.crs.authid():
                raise ValueError("{layer} different crs")

        # simple point list validation
        try:
            self.validate_point_list()
        except Exception as e:
            raise PreparationError(str(e)) from e

        try:
            self.prepare_paths()
        except Exception as e:
            self.roll_back()
            raise PreparationError(str(e)) from e

        try:
            self.run()
        except Exception as e:
            # something went wrong, cancel everything
            self.roll_back()
            raise TransformError(str(e)) from e

        if self.commit:
            # commit changes
            for layer in [self.line_layer] + self.other_layers:
                if layer.isEditable():
                    layer.commitChanges()

    def run(self):
        # find line fids and order the feature geometries
        for i in range(len(self.point_list) - 1):
            self.iteration = i
            # print("iteration", i)

            # help points from old line part
            self.start_point = self.point_list[i][0]
            self.end_point = self.point_list[i + 1][0]

            # help point for new line part
            self.new_start_point = self.point_list[i][1]
            self.new_end_point = self.point_list[i + 1][1]

            fids, self.use_poly_line = self.path_data[i]
            cached_features = [self.edit_feature_map[self.line_layer][fid] for fid in fids]

            # reload feature data from current qgis edit buffer/cache
            sorted_main_features = [self.line_layer.getFeature(fid) for fid in fids
                                    if fid not in self.edit_feature_map[self.line_layer]]
            sorted_main_features = sorted_main_features + cached_features
            self.sorted_main_features = sort_lines_features(sorted_main_features)
            old_poly_lines = [get_polyline(f.geometry()) for f in self.sorted_main_features]
            merged_full_old_line = []
            for old_poly_line in old_poly_lines:
                merged_full_old_line.extend(old_poly_line[:-1])
            merged_full_old_line.append(old_poly_lines[-1][-1])  # old needed path to transform

            # let's short the old merged line to start and end point
            index_start = get_point_index(self.start_point, merged_full_old_line)
            index_end = get_point_index(self.end_point, merged_full_old_line)
            index_from = min(index_start, index_end)
            index_to = max(index_start, index_end)
            self.merged_old_line = merged_full_old_line[index_from:index_to + 1]
            # bring the poly lines in same direction
            if not self.merged_old_line[0].compare(self.start_point, EPSILON):
                if not self.merged_old_line[0].compare(self.end_point, EPSILON):
                    raise ValueError("expecting correct other line end, but it isn't")
                self.merged_old_line.reverse()

            # find main path
            self.transform_vertices()
            self.prepare_connected_points()
            self.insert_remaining_vertices()

            # step transformation complete, reset next (i + 1) end point as new start point
            self.point_list[i + 1] = (self.new_end_point, self.new_end_point)

        # finalize :D
        self.finalize_geometries()

    def prepare_paths(self):

        # prepare the fids per iteration to prevent wrong path finding with QgsTracer
        # find line fids and order the feature geometries
        for i in range(len(self.point_list) - 1):
            # help points from old line part
            start_point = self.point_list[i][0]
            end_point = self.point_list[i + 1][0]

            # help point for new line part
            new_start_point = self.point_list[i][1]
            new_end_point = self.point_list[i + 1][1]
            try:
                index_from = min(get_point_index(new_start_point, self.new_poly_line),
                                 get_point_index(new_end_point, self.new_poly_line))
                index_to = max(get_point_index(new_start_point, self.new_poly_line),
                               get_point_index(new_end_point, self.new_poly_line))
            except ValueError as e:
                raise ValueError(str(e)) from e
            use_poly_line = self.new_poly_line[index_from:index_to + 1]

            # find the path with tracer
            poly = PathFinder.get_polyline_tracer(
                self.line_layer,
                start_point,
                end_point)

            if not poly:
                # try to use qgis processing (needs existing vertices on network layer too)
                poly = PathFinder.get_polyline_processing(
                    self.line_layer,
                    start_point,
                    end_point)

            if not poly:
                raise NoPathFoundError(f"Kein Pfad in Iteration {i} für Vorbereitung ermittelt. Linie: "
                                       f"{QgsGeometry.fromPolylineXY(poly).asWkt(TO_STRING_PREC)}")

            # find underlying features and select them
            line_layer_fids = get_feature_ids_containing(self.line_layer, poly)

            if not line_layer_fids:
                raise NoPathFoundError("Keine Features ermittelt mit Linie "
                                       f"{QgsGeometry.fromPolylineXY(poly).asWkt(TO_STRING_PREC)}")

            # get features and sort them starting with the first intersecting line feature
            features = []
            feature = None
            for fid in line_layer_fids:

                # per default use source feature
                f = self.line_layer.getFeature(fid)

                if fid not in self.source_geometry_map[self.line_layer]:
                    self.source_geometry_map[self.line_layer][fid] = f.geometry()  # backup

                if fid not in self.edit_feature_map[self.line_layer]:
                    # on this feature do the calculation
                    self.edit_feature_map[self.line_layer][fid] = QgsFeature(f)
                else:
                    # use cached feature
                    f = self.edit_feature_map[self.line_layer][fid]

                if is_point_on_line(start_point, get_polyline(f.geometry())) and feature is None:
                    # first feature from start
                    feature = f
                else:
                    # feature somewhere on route
                    features.append(f)
            # start feature must be found here!
            if feature is None:
                raise TypeError("QgsFeature/feature not found")

            features.insert(0, feature)

            sorted_main_features = sort_lines_features(features)

            self.path_data.append(
                ([f.id() for f in sorted_main_features], use_poly_line)
            )

    def validate_point_list(self):
        """ validates old and reference point list """

        for i, point_pair in enumerate(self.point_list):
            old_point, new_point = point_pair

            if not is_point_on_line(new_point, self.new_poly_line):
                raise PointNotOnPolyLineError(f"index {i} point {new_point} "
                                              f"not on poly line {self.new_poly_line}")

    def transform_vertices(self):
        """ create transform dict from old point to new point """
        # two times in usage
        old_wrapper = PolylineWrapper.from_point_list(self.merged_old_line)
        new_wrapper = PolylineWrapper.from_point_list(self.use_poly_line)

        # factor from old to new
        factor = new_wrapper.length() / old_wrapper.length()

        # map old point to new point
        # ignore first and last point, because they will not change (start/end point still on old line)
        for old_point in self.merged_old_line[1:-1]:
            new_distance = old_wrapper.get_distance_on_line(old_point) * factor
            new_point = new_wrapper.insert_point_in_line(new_distance)
            self.transform_point_map[old_point.toString(TO_STRING_PREC)] = new_point

        self.transform_point_map[self.merged_old_line[0].toString(TO_STRING_PREC)] = self.use_poly_line[0]
        self.transform_point_map[self.merged_old_line[-1].toString(TO_STRING_PREC)] = self.use_poly_line[-1]

        # clear current mutable list and extend it with new points
        self.use_poly_line.clear()
        self.use_poly_line.extend(new_wrapper.as_point_list())

    def prepare_connected_points(self):
        """ prepares connected point, that have to moved later """
        bounding = QgsGeometry.fromPolylineXY(self.merged_old_line).boundingBox()
        request = QgsFeatureRequest().setFilterRect(bounding)

        # iterate over each layer
        for layer in [self.line_layer] + self.other_layers:

            for feature in layer.getFeatures(request):
                self.handle_feature(layer, feature)

    def handle_feature(self, layer: QgsVectorLayer, feature: QgsFeature):
        """ handles features geometry """
        type_ = layer.wkbType()

        if type_ in [QgsWkbTypes.Point, QgsWkbTypes.MultiPoint]:
            # handle point geometry
            point = get_point(feature.geometry())
            point_str = point.toString(TO_STRING_PREC)
            if point_str in self.transform_point_map:

                if feature.id() not in self.source_geometry_map:
                    # save original source geometry
                    self.source_geometry_map[layer][feature.id()] = feature.geometry()

                if feature.id() not in self.edit_feature_map:
                    # save original source geometry
                    feature.setGeometry(QgsGeometry.fromPointXY(
                        self.transform_point_map[point_str]))
                    self.edit_feature_map[layer][feature.id()] = QgsFeature(feature)

            return

        if type_ in [QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString]:
            # handle line geometry
            new_poly_line = []
            to_update = False

            poly_line = get_polyline(feature.geometry())

            # add touching lines
            self.handle_touching_line(poly_line[0])
            self.handle_touching_line(poly_line[-1])

            for point in poly_line:
                point_str = point.toString(TO_STRING_PREC)

                if point_str in self.transform_point_map:
                    to_update = True
                    new_point = self.transform_point_map[point_str]
                else:
                    new_point = point

                if new_point not in new_poly_line:
                    new_poly_line.append(new_point)

            if to_update:
                # is a connected line on old vertex

                if feature.id() not in self.source_geometry_map:
                    # save original source geometry
                    self.source_geometry_map[layer][feature.id()] = feature.geometry()

                if feature.id() not in self.edit_feature_map:
                    # save original source geometry
                    feature.setGeometry(QgsGeometry.fromPolylineXY(new_poly_line))
                    self.edit_feature_map[layer][feature.id()] = QgsFeature(feature)

            return

        raise ValueError(f"{layer} has unknown wkbType()")

    def handle_touching_line(self, point: QgsPointXY):
        """ Handle touching points (start or end point) from line.

        """
        if is_point_in_polylist(point, self.merged_old_line):
            # already in old list
            return

        if not is_point_on_line(point, self.merged_old_line, EPSILON_METRES):
            # not on old line
            return

        # add touch point to current merged old line
        old_wrapper = PolylineWrapper.from_point_list(self.merged_old_line)
        new_wrapper = PolylineWrapper.from_point_list(self.use_poly_line)

        # factor from old to new
        factor = new_wrapper.length() / old_wrapper.length()

        # map old point to new point
        new_distance = old_wrapper.get_distance_on_line(point) * factor
        new_point = new_wrapper.insert_point_in_line(new_distance)
        self.transform_point_map[point.toString(TO_STRING_PREC)] = new_point
        self.merged_old_line = old_wrapper.as_point_list()

    def correct_part(self, part: List[QgsPointXY]) -> Optional[int]:
        """ corrects part and maybe reverse it, only when current main path has only one geometry/feature """
        if not part:
            # do nothing, is empty
            return None

        if self.start_point in part:
            # first_part
            # last part point equals old start point and first point from new poly line equals new start point,
            # so then the first point from part has to be equal to old start -> then reverse the line
            if self.use_poly_line[0].compare(self.new_start_point, EPSILON) \
                and (not part[-1].compare(self.start_point, EPSILON)
                     and part[0].compare(self.start_point, EPSILON)):
                part.reverse()
            return N_LEFT

        if self.end_point in part:
            # last_part
            # first part point equals old end point and last point from new poly line equals new start point,
            # so then the first point from part has to be equal to old start -> then reverse the line
            if self.use_poly_line[-1].compare(self.new_end_point, EPSILON) \
                and (not part[0].compare(self.end_point, EPSILON)
                     and part[-1].compare(self.end_point, EPSILON)):
                part.reverse()
            return N_RIGHT

        # unknown fall back handling :o
        if part[0].compare(self.use_poly_line[-1]):
            return N_RIGHT

        # unknown fall back handling :o
        if part[-1].compare(self.use_poly_line[0]):
            return N_LEFT

        # WARNING: unknown behaviour for poly line handling if side is missing :(

        return None

    def get_needed_part(self, poly: List[QgsPointXY],
                        split_point: QgsPointXY) -> Tuple[Optional[List[QgsPointXY]],
                                                          Optional[int]]:
        """ returns needed part depending on current self.use_poly_line """

        part_one = poly[:get_point_index(split_point, poly) + 1]
        part_two = poly[get_point_index(split_point, poly):]

        part = None
        side = None

        if len(part_one) > 1:
            if part_one[1] in self.merged_old_line:
                # one point of part_one is in old merged_old_line, use part_two
                part = part_two

        if len(part_two) > 1:
            if part_two[1] in self.merged_old_line:
                # one point of part_two is in old merged_old_line, use part_one
                part = part_one

        if part:
            side = self.correct_part(part)

        return part, side

    def get_needed_use_poly_line_part(self, poly, point):
        """ returns only the needed part from self.use_poly_line if this is partially used by a transformation """
        first_str = poly[0].toString(TO_STRING_PREC)
        last_str = poly[-1].toString(TO_STRING_PREC)

        part_one = None
        part_two = None
        use_point = None

        # first and last are not allowed to be the first/last in poly line
        if first_str in self.transform_point_map:
            first = self.transform_point_map[first_str]
            if is_point_in_polylist(first, self.use_poly_line[1:-1]):
                part_one = poly[:get_point_index(point, poly) + 1]
                part_two = poly[get_point_index(point, poly):]
                use_point = first

        # last point is somewhere on the new poly line
        # get only the projected segment from old poly to new poly line
        if last_str in self.transform_point_map:
            last = self.transform_point_map[last_str]
            if is_point_in_polylist(last, self.use_poly_line[1:-1]) and use_point is None:
                part_one = poly[:get_point_index(point, poly) + 1]
                part_two = poly[get_point_index(point, poly):]
                use_point = last

        if use_point:
            # do my stuff and parts are defined
            use_part = None
            for part in [part_one, part_two]:
                if len(part) < 2:
                    continue

                if all((p.toString(TO_STRING_PREC) in self.transform_point_map) for p in part):
                    # each point already transformed
                    # from qgis.PyQt.QtGui import QGuiApplication
                    # clipboard = QGuiApplication.clipboard()
                    # clipboard.setText(str({k: v.toString(TO_STRING_PREC) for k, v in self.transform_point_map.items()}))
                    use_part = [self.transform_point_map[p.toString(TO_STRING_PREC)] for p in part]
                    break

            if use_part:
                # transformed part
                index_from = min(get_point_index(use_part[0], self.use_poly_line),
                                 get_point_index(use_part[-1], self.use_poly_line))
                index_to = max(get_point_index(use_part[0], self.use_poly_line),
                               get_point_index(use_part[-1], self.use_poly_line))
                use_part = self.use_poly_line[index_from: index_to + 1]
                return use_part

        # default
        return self.use_poly_line

    def insert_remaining_vertices(self):
        """ ... """
        for feature in self.sorted_main_features:
            geometry = feature.geometry()
            fid = feature.id()
            poly = get_polyline(geometry)

            # only one geometry to change
            if is_point_on_line(self.start_point, poly) and is_point_on_line(self.end_point, poly):

                index_from = min(get_point_index(self.start_point, poly),
                                 get_point_index(self.end_point, poly))
                index_to = max(get_point_index(self.start_point, poly),
                               get_point_index(self.end_point, poly))

                first_part = poly[:index_from + 1]
                if len(first_part) == 1:
                    first_part = []

                last_part = poly[index_to:]
                if len(last_part) == 1:
                    last_part = []

                # test if one of the lines must be reversed
                first_side = self.correct_part(first_part)

                # test if one of the lines must be reversed
                last_side = self.correct_part(last_part)

                if first_side is not None and first_side == last_side:
                    raise ValueError("wow, same side not allowed :(")

                if last_side is None and first_side is None:
                    # no side present :o
                    # print("no side present")
                    use_poly_line = self.use_poly_line
                elif last_side is not None and first_side is None:
                    # only last side present
                    # print("last_side present with", last_side)
                    if last_side == N_LEFT:
                        use_poly_line = last_part + self.use_poly_line
                    else:
                        use_poly_line = self.use_poly_line + last_part
                elif last_side is None and first_side is not None:
                    # only first side present
                    # print("first_side present with", first_side)
                    if first_side == N_LEFT:
                        use_poly_line = first_part + self.use_poly_line
                    else:
                        use_poly_line = self.use_poly_line + first_part
                else:
                    # both sides are present
                    # print("both sides present with", f"first_side={first_side}", f"last_side={last_side}")
                    use_poly_line = self.use_poly_line.copy()
                    if first_side == N_LEFT:
                        use_poly_line = first_part + use_poly_line
                    else:
                        use_poly_line = use_poly_line + first_part

                    if last_side == N_LEFT:
                        use_poly_line = last_part + use_poly_line
                    else:
                        use_poly_line = use_poly_line + last_part

                new_poly = []
                for point in use_poly_line:
                    if point not in new_poly:
                        new_poly.append(point)

                self.edit_feature_map[self.line_layer][fid].setGeometry(
                    QgsGeometry.fromPolylineXY(new_poly))
                continue

            # only the first part has an intersection
            if is_point_on_line(self.start_point, poly) and is_point_in_polylist(self.start_point, poly[1:-1], EPSILON):
                # print("only start point")
                part, side = self.get_needed_part(poly, self.start_point)

                use_poly_line = self.get_needed_use_poly_line_part(poly, self.start_point)
                if side == N_LEFT:
                    use_poly_line = part + use_poly_line
                elif side == N_RIGHT:
                    use_poly_line = use_poly_line + part
                else:
                    raise ValueError(f"side and part not valid {part, side}")

                new_poly = []
                for point in use_poly_line:
                    if point not in new_poly:
                        new_poly.append(point)

                self.edit_feature_map[self.line_layer][fid].setGeometry(
                    QgsGeometry.fromPolylineXY(new_poly)
                )
                continue

            # only the last part has an intersection
            if is_point_on_line(self.end_point, poly) and is_point_in_polylist(self.end_point, poly[1:-1], EPSILON):
                # print("only end point")
                part, side = self.get_needed_part(poly, self.end_point)

                use_poly_line = self.get_needed_use_poly_line_part(poly, self.end_point)
                if side == N_LEFT:
                    use_poly_line = part + use_poly_line
                elif side == N_RIGHT:
                    use_poly_line = use_poly_line + part
                else:
                    raise ValueError(f"side and part not valid {part, side}")

                new_poly = []
                for point in use_poly_line:
                    if point not in new_poly:
                        new_poly.append(point)

                self.edit_feature_map[self.line_layer][fid].setGeometry(
                    QgsGeometry.fromPolylineXY(new_poly))
                continue

            # print("default handling")
            # no intersection with start or end point
            # uses full part from new_poly_line as new geometry
            start_g_point = self.transform_point_map[poly[0].toString(TO_STRING_PREC)]
            start_g_index = get_point_index(start_g_point, self.use_poly_line)
            end_g_point = self.transform_point_map[poly[-1].toString(TO_STRING_PREC)]
            end_g_index = get_point_index(end_g_point, self.use_poly_line)
            new_poly = []
            for p in self.use_poly_line[min(start_g_index, end_g_index):max(start_g_index, end_g_index) + 1]:
                if p not in new_poly:
                    new_poly.append(p)
            self.edit_feature_map[self.line_layer][fid].setGeometry(
                QgsGeometry.fromPolylineXY(new_poly))

    def finalize_geometries(self):
        """ updates geometries in layer """

        for layer, feature_map in self.edit_feature_map.items():

            if not layer.isEditable():
                layer.startEditing()
                layer.beginEditCommand("update")

            is_line_type = layer.geometryType() == QgsWkbTypes.LineGeometry

            for fid, feature in feature_map.items():

                if is_line_type:
                    # remove duplicates
                    geometry = feature.geometry().simplify(EPSILON_METRES * 0.001)
                else:
                    geometry = feature.geometry()

                if not layer.changeGeometry(fid, geometry):
                    raise ValueError("geometry not saved")

            layer.endEditCommand()

    def roll_back(self):
        """ Roll back all changes made with this class.
            Only use this method, when other geometry operations
            are not possible to prevent roll back conflicts.
        """
        for layer in [self.line_layer] + self.other_layers:
            try:
                geometry_map = self.source_geometry_map[layer]

                if layer.isEditable():
                    layer.rollBack()
                else:
                    # layer not in editing mode, restore old features with backup map
                    # directly with dataprovider
                    layer.dataProvider().changeGeometryValues(geometry_map)
            except Exception as e:
                raise RollbackError(f"roll back failed for {layer.id()} with exception {e}") from e

    @classmethod
    def from_new_poly_line(cls, poly_line: List[QgsPointXY],
                           main_layer: QgsVectorLayer,
                           other_layers: Optional[List[QgsVectorLayer]] = None,
                           commit: bool = False):
        """ initialize transform tool from given poly line, main layer.
            Polyline's coordinates must be in main_layer crs.
            And must touch or intersect with main_layer (line layer)
        """

        # pairs [(((start_main_fid, start_main_point), (start_ref_fid, start_ref_point)),
        #         ((end_main_fid, end_main_point), (end_ref_fid, end_ref_point)))]
        wrapper = PolylineWrapper.from_point_list(poly_line)
        first = poly_line[0]
        last = poly_line[-1]

        geometry = QgsGeometry.fromPolylineXY(poly_line)
        rect = geometry.boundingBox().scaled(1.1)
        request = QgsFeatureRequest().setFilterRect(rect)
        points: List[Tuple[float, QgsPointXY, int]] = []
        for f in main_layer.getFeatures(request):
            # features geometry
            f_geom = f.geometry()

            # add points for intersection
            intersection = f_geom.intersection(geometry)
            if not intersection.isEmpty() and not intersection.isNull():
                points.extend([(0.0, p, f.id()) for p in get_multi_point(intersection)])

            # add points from touching
            if is_point_on_line(first, get_polyline(f_geom)):
                points.append((0.0, first, f.id()))

            if is_point_on_line(last, get_polyline(f_geom)):
                points.append((0.0, last, f.id()))

        for i, x in enumerate(points):
            y, point, fid = x
            dist = wrapper.get_distance_on_line(point)

            if is_point_in_polylist(point, poly_line, EPSILON):
                # already in poly list, use same point from existing line to prevent rounding issues
                index = get_point_index(point, poly_line)
                points[i] = (dist, poly_line[index], fid)
                continue

            if dist > wrapper.length():
                # whoops?
                points[i] = (wrapper.length(), poly_line[-1], fid)
                continue

            new_point = wrapper.insert_point_in_line(dist)
            points[i] = (dist, new_point, fid)

        poly_line = wrapper.as_point_list()

        points.sort(key=lambda z: z[0])
        if len(points) < 2:
            raise ValueError("Neue Linie fehlerhaft - ungenügend Berührungen/Überschneidungen")

        if points[0][1].compare(points[-1][1], EPSILON_METRES):
            raise ValueError("Neue Linie fehlerhaft, erster und letzter Punkt identisch")

        # split down the given poly line
        poly_line = poly_line[poly_line.index(points[0][1]):poly_line.index(points[-1][1]) + 1]
        params = [(poly_line[0], poly_line[0]), (poly_line[-1], poly_line[-1])]
        add_vertices([(points[0][2], points[0][1]), (points[-1][2], points[-1][1])],
                     main_layer,
                     commit=commit)

        return cls(params, poly_line, main_layer, other_layers=other_layers, commit=commit)

    @classmethod
    def from_reference_layer(cls, geometries: List[QgsGeometry],
                             main_layer: QgsVectorLayer, reference_layer: QgsVectorLayer,
                             other_layers: Optional[List[QgsVectorLayer]] = None,
                             commit: bool = False):
        """ initialize transform tool from geometry tuples, main layer and reference layer """

        # pairs [(((start_main_fid, start_main_point), (start_ref_fid, start_ref_point)),
        #         ((end_main_fid, end_main_point), (end_ref_fid, end_ref_point)))]
        params = []
        main_layer_points = []
        ref_layer_points = []

        # add missing vertices on main layer
        for i, geometry in enumerate(geometries):
            inter_main_and_ref = get_points_from_help_line(geometry, main_layer, reference_layer)
            if inter_main_and_ref is None:
                raise NoIntersectionFoundError(f"inter_main_and_ref > get_points_from_help_line failed on index {i} "
                                               f"with geometry {geometry}")
            main_layer_points.append(inter_main_and_ref[0])

            ref_layer_points.append(inter_main_and_ref[1])

            params.append((inter_main_and_ref[0][1], inter_main_and_ref[1][1]))

        if not params:
            raise ValueError("no pairs found or geometry list is empty")

        # transform ref_layer_points points to ref layer crs
        ref_layer_points = [(fid, transform_point(point,
                                                  main_layer.dataProvider().crs(),
                                                  reference_layer.dataProvider().crs()))
                            for fid, point in ref_layer_points]

        # add vertices to layer
        add_vertices(main_layer_points, main_layer, commit=commit)
        add_vertices(ref_layer_points, reference_layer, commit=commit)

        # find the path with tracer
        new_poly_line = PathFinder.get_polyline_tracer(
            reference_layer,
            ref_layer_points[0][1],
            ref_layer_points[-1][1])

        new_poly_line = [transform_point(point,
                                         reference_layer.dataProvider().crs(),
                                         main_layer.dataProvider().crs())
                         for point in new_poly_line]

        if not new_poly_line:
            for layer in [main_layer, reference_layer] + other_layers:
                if layer.isEditable():
                    layer.rollBack()
            raise NoPathFoundError(f"no path found from {ref_layer_points[0][1]} "
                                   f"to {ref_layer_points[-1][1]} on {reference_layer.name()}")

        # insert start and end point from main layer
        new_poly_line.insert(0, main_layer_points[0][1])
        new_poly_line.append(main_layer_points[-1][1])

        return cls(params, new_poly_line, main_layer, other_layers=other_layers, commit=commit)

    @classmethod
    def get_preview_layers_from_reference_layer(cls, geometries: List[QgsGeometry],
                                                main_layer: QgsVectorLayer, reference_layer: QgsVectorLayer,
                                                other_layers: Optional[List[QgsVectorLayer]] = None):
        """ Gets temporary preview layers.
            These can be used to calculate a transform preview.

            Hint: It expects, that the calculated bounding box of all geometries
                  will contain all needed features.
        """

        # combine geometries to get a multi type geometry
        geometry = QgsGeometry(geometries[0])
        for geom in geometries[1:]:
            geometry = geometry.combine(geom)

        # use bounding boxes from combined geometries
        ref_geometry = transform_geometry(geometry,
                                          main_layer.dataProvider().crs(),
                                          reference_layer.dataProvider().crs())

        # use a bigger rectangle
        request = QgsFeatureRequest().setFilterRect(geometry.boundingBox().scaled(2.0))
        request_ref = QgsFeatureRequest().setFilterRect(ref_geometry.boundingBox().scaled(2.0))

        # make layers temporary
        main_layer = main_layer.materialize(request)
        other_layers = [layer.materialize(request) for layer in other_layers]
        reference_layer = reference_layer.materialize(request_ref)

        return main_layer, reference_layer, other_layers

    @staticmethod
    def is_layer_compatible(layer: QgsVectorLayer):
        return isinstance(layer, QgsVectorLayer) and layer.wkbType() in [QgsWkbTypes.Point, QgsWkbTypes.LineString,
                                                                         QgsWkbTypes.MultiPoint,
                                                                         QgsWkbTypes.MultiLineString]

    def create_test_layer(self, poly_line, name):
        templayer = QgsVectorLayer(f"LineString?crs={self.crs.authid()}", name + " /" + str(self.iteration), "memory")
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPolylineXY(poly_line))
        templayer.dataProvider().addFeatures([f])
        QgsProject.instance().addMapLayer(templayer)
