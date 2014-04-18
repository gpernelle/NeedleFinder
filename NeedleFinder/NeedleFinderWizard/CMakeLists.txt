set(KIT_PYTHON_MODULE_NAME NeedleFinderWizard)

set(KIT_PYTHON_SCRIPTS
  __init__.py
  Helper.py
  NFStep.py
  NFSelectProcedureStep.py
  NFSelectApplicatorStep.py
  NFLoadModelStep.py
  NFFirstRegistrationStep.py
  NFSecondRegistrationStep.py
  NFNeedlePlanningStep.py
  NFNeedleSegmentationStep.py
  )

set(KIT_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME ${EXTENSION_NAME}${KIT_PYTHON_MODULE_NAME}
  SCRIPTS "${KIT_PYTHON_SCRIPTS}"
  RESOURCES "${KIT_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/${KIT_PYTHON_MODULE_NAME}
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/${KIT_PYTHON_MODULE_NAME}
  NO_INSTALL_SUBDIR
  )
