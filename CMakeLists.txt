cmake_minimum_required(VERSION 2.8.9)

project(NeedleFinder)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/gpernelle/NeedleFinder")
set(EXTENSION_CATEGORY "IGT")

set(EXTENSION_CONTRIBUTORS "Guillaume Pernelle,  Alireza Mehrtash, Lauren Barber, Nabgha Fahrat, Jan Egger, Tobias Penzkofer, Sandy Wells, Sam Song, Xiaojun Chen, Yi Gao, Antonio Damato, Tina Kapur, Akila Viswanathan")

set(EXTENSION_DESCRIPTION "NeedleFinder: fast interactive needle detection. It provides interactive tools to segment needles in MR/CT images. It has been mostly tested on MRI from gynelogical brachytherapy cases. Cf <<Validation of Catheter Segmentation for MR-Guided Gynecologic Cancer Brachytherapy.>> MICCAI 2013")

set(EXTENSION_ICONURL "https://raw.github.com/gpernelle/NeedleFinder/master/NeedleFinder.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.github.com/gpernelle/NeedleFinder/master/screenshot.png")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(NeedleFinder)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
