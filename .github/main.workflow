name: Python package

on: [push]

jobs:
  build:

    runs-on: ubuntu-latest
    strategy:
      max-parallel: 4
      matrix:
        python-version: [2.7, 3.5, 3.6, 3.7]

    steps:
    - uses: actions/checkout@master
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v1
      with:
        version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip wheel
        pip install -U -r requirements-test.txt -r requirements-ci.txt
    - name: Test with pytest
      run: |
        pip install pytest
        py.test --cov=translation_finder translation_finder README.rst
