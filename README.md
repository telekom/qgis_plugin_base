<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom AG

SPDX-License-Identifier: CC0-1.0    
-->

# QGIS Plugin Base

[![GNU GPLv3](https://img.shields.io/badge/license-%20%20GNU%20GPLv3%20-green?style=plastic)](https://img.shields.io/badge/license-%20%20GNU%20GPLv3%20-green?style=plastic)
[![REUSE Compliance Check](https://github.com/telekom/qgis_plugin_base/actions/workflows/reuse-compliance.yml/badge.svg)](https://github.com/telekom/qgis_plugin_base/actions/workflows/reuse-compliance.yml)
[![OpenSSF Scorecard Score](https://api.scorecard.dev/projects/github.com/telekom/qgis_plugin_base/badge)](https://scorecard.dev/viewer/?uri=github.com/telekom/qgis_plugin_base/badge)

## About

A code base with usefull code and test examples, which a QGIS plugin can use.

## QGIS Version

A lot of the available functions may work only with the latest QGIS LTR version.

Last tested with QGIS version: 3.40.7

## Technical Depths

- a lot of error messages are written in German
- a lot of docstrings and comments are written in German
- missing tests (current intention is not to add blindly a lot of test, only when it is necessary for already available functions.)
  - tests required for new functions
- Some code is related to the Windows OS

## Test Automation with pytest

Some tests may require a different setup or must fulfill some requirements.

Do not use the pytest plugin `pytest-qgis`. This may result in some mock issues.

### Environment Variable `QGIS_PYTEST_AUTHENTICATION_CONFIG_DIR`

Using the fixture `plugin_qgis_new_project` from [./tests/fixtures.py](./tests/fixtures.py) can use the OS environment variable `QGIS_PYTEST_AUTHENTICATION_CONFIG_DIR` 
to load authentication configuration files to the temporary QGIS instance.

If set the variable value should point to an existing directory with un-encrypted config files (XML).

Example value: `C:/dev/.pytest-qgis-credentials`

Example structure:

* C:/dev/.pytest-qgis-credentials
  * credentials-gdi-basic-auth.xml (not encrypted)

Maybe some tests require this variable to be set.

## Code of Conduct

This project has adopted the [Contributor Covenant](https://www.contributor-covenant.org/) in version 2.1 as our code of conduct. Please see the details in our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). All contributors must abide by the code of conduct.

By participating in this project, you agree to abide by its [Code of Conduct](./CODE_OF_CONDUCT.md) at all times.

## Licensing
Copyright (c) 2025 Deutsche Telekom AG

All content in this repository is licensed under at least one of the licenses found in [./LICENSES](./LICENSES); you may not use this file, or any other file in this repository, except in compliance with the Licenses. 
You may obtain a copy of the Licenses by reviewing the files found in the [./LICENSES](./LICENSES) folder.

Unless required by applicable law or agreed to in writing, software distributed under the Licenses is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See in the [./LICENSES](./LICENSES) folder for the specific language governing permissions and limitations under the Licenses.

This project follows the [REUSE standard for software licensing](https://reuse.software/). 
Each file contains copyright and license information, and license texts can be found in the [./LICENSES](./LICENSES) folder. For more information visit https://reuse.software/.
You can find a guide for developers at https://telekom.github.io/reuse-template/.
