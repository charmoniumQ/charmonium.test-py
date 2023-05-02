==========================
charmonium.test-py
==========================

.. image:: https://img.shields.io/pypi/v/charmonium.test_py
   :alt: PyPI Package
   :target: https://pypi.org/project/charmonium.test_py
.. image:: https://img.shields.io/pypi/dm/charmonium.test_py
   :alt: PyPI Downloads
   :target: https://pypi.org/project/charmonium.test_py
.. image:: https://img.shields.io/pypi/l/charmonium.test_py
   :alt: License
   :target: https://github.com/charmoniumQ/charmonium.test-py/blob/main/LICENSE
.. image:: https://img.shields.io/pypi/pyversions/charmonium.test_py
   :alt: Python Versions
   :target: https://pypi.org/project/charmonium.test_py
.. image:: https://img.shields.io/librariesio/sourcerank/pypi/charmonium.test_py
   :alt: libraries.io sourcerank
   :target: https://libraries.io/pypi/charmonium.test_py

.. image:: https://img.shields.io/github/stars/charmoniumQ/charmonium.test-py?style=social
   :alt: GitHub stars
   :target: https://github.com/charmoniumQ/charmonium.test-py
.. image:: https://github.com/charmoniumQ/charmonium.test-py/actions/workflows/main.yaml/badge.svg
   :alt: CI status
   :target: https://github.com/charmoniumQ/charmonium.test-py/actions/workflows/main.yaml
.. image:: https://img.shields.io/github/last-commit/charmoniumQ/charmonium.test-py
   :alt: GitHub last commit
   :target: https://github.com/charmoniumQ/charmonium.test-py/commits
.. image:: http://www.mypy-lang.org/static/mypy_badge.svg
   :target: https://mypy.readthedocs.io/en/stable/
   :alt: Checked with Mypy
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code style: black

Test python projects automatically.

----------
Quickstart
----------

If you don't have ``pip`` installed, see the `pip install guide`_.

.. _`pip install guide`: https://pip.pypa.io/en/latest/installing/

.. code-block:: console

    $ pip install charmonium.test-py

>>> import charmonium.test_py


See `CONTRIBUTING.md`_ for instructions on setting up a development environment.

.. _`CONTRIBUTING.md`: https://github.com/charmoniumQ/charmonium.test-py/tree/main/CONTRIBUTING.md

----
TODO
----

- Make freeze_config a parameter to charmonium.cache.
- Add function-version annotation to charmonium.cache/charmonium.freeze.
- Add a way to query the current hash of a function or class. It should work in the decorator as a "don't invalidate the last run".
- Ignore pure functions in stdlib except exceptions.
- In FileBundle, store the contained files in a separate location or inline based on its size.
- Consider the case where delayed function calls cached function calls delayed function. Is this cached correctly? In particular, we should not freeze Dask's global scheduler.
- Deploy the new code more carefully.
- Should we switch to a batch scheduler?
- Write local and remote config files.
- Consider bare-metal + Nix instead of Docker container for Dask workers and manager.
- Write Python and R experiment config files.
- Review ``secrets.env``
