if (MODEL STREQUAL gptl)
  string(APPEND CPPDEFS " -DHAVE_VPRINTF -DHAVE_TIMES -DHAVE_GETTIMEOFDAY")
endif()
string(APPEND SLIBS " -lnetcdff -lnetcdf -mkl")
if (DEBUG)
  string(APPEND FFLAGS " -ftrapuv")
endif()
if (DEBUG)
  string(APPEND CFLAGS " -ftrapuv")
endif()
set(NETCDF_PATH "$ENV{NETCDF_DIR}")
set(LAPACK_LIBDIR "/global/software/sl-6.x86_64/modules/intel/2016.1.150/lapack/3.6.0-intel/lib")
