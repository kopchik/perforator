#!/usr/bin/env python3
from distutils.extension import Extension
from distutils.core import setup
from Cython.Distutils import build_ext

_perf = Extension('_perf',
                    sources = ['_perf.c'], extra_compile_args=["-std=gnu99"])
setup(
  name = 'Perforator library functions',
  cmdclass = {'build_ext': build_ext},
  # ext_modules = cythonize("perflib.pyx"),
  ext_modules = [Extension('perflib',['perflib.pyx']), _perf]
)
