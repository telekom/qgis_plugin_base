# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest

from qgis.core import QgsVectorLayer, QgsVectorDataProvider

from .fixtures import simple_point_vector_layer, get_test_point_feature

READ_ONLY = "read-only"
WRITE = "write"


def _handle_read_only_mode(layer: QgsVectorLayer, mode: str):
    if mode == READ_ONLY:
        assert layer.setReadOnly(True)

    # set edit mode
    if mode == READ_ONLY:
        assert not layer.startEditing()
    elif mode == WRITE:
        assert layer.startEditing()


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_addFeature(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.addFeature(new_test_feature)
    elif mode == WRITE:
        assert simple_point_vector_layer.addFeature(new_test_feature)


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_updateFeature(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    feature_1["id"] = 999999

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.updateFeature(feature_1)
    elif mode == WRITE:
        assert simple_point_vector_layer.updateFeature(feature_1)


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_addFeatures(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.addFeatures([new_test_feature])
    elif mode == WRITE:
        assert simple_point_vector_layer.addFeatures([new_test_feature])


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_changeGeometry(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.changeGeometry(feature_1.id(), new_test_feature.geometry())
    elif mode == WRITE:
        assert simple_point_vector_layer.changeGeometry(feature_1.id(), new_test_feature.geometry())


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_changeAttributeValue(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.changeAttributeValue(feature_1.id(), 0, 99999999)
    elif mode == WRITE:
        assert simple_point_vector_layer.changeAttributeValue(feature_1.id(), 0, 99999999)


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_changeAttributeValues(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.changeAttributeValues(feature_1.id(), {0: 99999999})
    elif mode == WRITE:
        assert simple_point_vector_layer.changeAttributeValues(feature_1.id(), {0: 99999999})


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_deleteFeature(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.deleteFeature(feature_1.id())
    elif mode == WRITE:
        assert simple_point_vector_layer.deleteFeature(feature_1.id())


@pytest.mark.parametrize("mode", [READ_ONLY, WRITE])
def test_vector_layer_deleteFeatures(simple_point_vector_layer: QgsVectorLayer, mode: str):
    # handle the read-only mode
    _handle_read_only_mode(simple_point_vector_layer, mode)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    feature_2 = next(features)
    assert feature_1.isValid()
    assert feature_2.isValid()

    if mode == READ_ONLY:
        assert not simple_point_vector_layer.deleteFeatures([feature_1.id(), feature_2.id()])
    elif mode == WRITE:
        assert simple_point_vector_layer.deleteFeatures([feature_1.id(), feature_2.id()])


def test_vector_provider_read_only_addFeature(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)
    assert provider.addFeature(new_test_feature)


def test_vector_provider_read_only_addFeatures(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    new_test_feature_1 = get_test_point_feature(simple_point_vector_layer)
    new_test_feature_2 = get_test_point_feature(simple_point_vector_layer)
    assert provider.addFeatures([new_test_feature_1, new_test_feature_2])[0]


def test_vector_provider_read_only_changeAttributeValues(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    provider.changeAttributeValues({feature_1.id(): {0: 99999}})


def test_vector_provider_read_only_changeFeatures(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)

    assert provider.changeFeatures({feature_1.id(): {0: 99999}}, {feature_1.id(): new_test_feature.geometry()})


def test_vector_provider_read_only_changeGeometryValues(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    assert feature_1.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    new_test_feature = get_test_point_feature(simple_point_vector_layer)

    assert provider.changeGeometryValues({feature_1.id(): new_test_feature.geometry()})


def test_vector_provider_read_only_deleteFeatures(simple_point_vector_layer: QgsVectorLayer):
    # ggf. auch Test dazu zu verstehen, dass QGIS nicht einfach die Funktionsweise ändert.
    #   Ist der Vektorlayer im readOnly(True)-Status, sollen weiterhin Änderungen über den Provider möglich sein.
    # set the layer in the read-only mode
    simple_point_vector_layer.setReadOnly(True)

    # get one of the test features
    features = simple_point_vector_layer.getFeatures()
    feature_1 = next(features)
    feature_2 = next(features)
    assert feature_1.isValid()
    assert feature_2.isValid()

    provider: QgsVectorDataProvider = simple_point_vector_layer.dataProvider()

    assert provider.deleteFeatures([feature_1.id(), feature_2.id()])
