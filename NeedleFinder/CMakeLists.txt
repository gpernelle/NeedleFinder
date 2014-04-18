#-----------------------------------------------------------------------------
set(MODULE_NAME NeedleFinder)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  ${MODULE_NAME}Wizard/__init__.py
  ${MODULE_NAME}Wizard/Helper.py
  ${MODULE_NAME}Wizard/NFStep.py
  ${MODULE_NAME}Wizard/NFFirstRegistrationStep.py
  ${MODULE_NAME}Wizard/NFLoadModelStep.py
  ${MODULE_NAME}Wizard/NFNeedlePlanningStep.py
  ${MODULE_NAME}Wizard/NFNeedleSegmentationStep.py
  ${MODULE_NAME}Wizard/NFSecondRegistrationStep.py
  ${MODULE_NAME}Wizard/NFSelectApplicatorStep.py
  ${MODULE_NAME}Wizard/NFSelectProcedureStep.py
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  )

