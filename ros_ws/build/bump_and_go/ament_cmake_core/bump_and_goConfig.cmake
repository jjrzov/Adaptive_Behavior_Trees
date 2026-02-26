# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_bump_and_go_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED bump_and_go_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(bump_and_go_FOUND FALSE)
  elseif(NOT bump_and_go_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(bump_and_go_FOUND FALSE)
  endif()
  return()
endif()
set(_bump_and_go_CONFIG_INCLUDED TRUE)

# output package information
if(NOT bump_and_go_FIND_QUIETLY)
  message(STATUS "Found bump_and_go: 0.0.0 (${bump_and_go_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'bump_and_go' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${bump_and_go_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(bump_and_go_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${bump_and_go_DIR}/${_extra}")
endforeach()
