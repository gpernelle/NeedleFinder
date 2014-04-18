iGyne
=====
***
This code is associated with the MICCAI 2013 publication "**Validation of Catheter Segmentation for MR-guided Gynecologic Cancer Brachytherapy**" from Guillaume Pernelle, Alireza Mehrtash, Lauren Barber, Antonio Damato,Wei Wang, Ravi Teja Seethamraju, Ehud Schmidt, Robert Cormack, Williams Wells, Akila Viswanathan, Tina Kapur.
*Medical Image Computing and Computer-Assisted Intervention–MICCAI 2013*, pp. 380-387. Springer Berlin Heidelberg, 2013.
***

**iGyne** is currently articulated in seven steps: 
1) procedure selection
2) applicator selection
3) data importation
4) initial applicator registration
5) refined applicator registration
6) needle position planning
7) needle detection
It offers also a way to go directly from 1) to 7), skipping the registration/planning steps

- iGyneSelectProcedureStep.py (1) and iGyneSelectApplicatorStep.py (2) let you choose to use or not an applicator, and to select the most convenient one. There are different configurations for the fiducial markers: 
* 4 landmarks, ordered from the top left corner and counting counter-clockwise (new cases)
* 3 landmarks, positioned at the corners of the template, ordered as above
* 3 landmarks, starting from the one in the middle of the template and counting counter-clockwise
This step offers an automatic registration option if the CLI module Hough Transformed has been previously enabled

- iGyneLoadModelStep.py (3) let you load the data while the scene is loaded depending on the made in step 2.

- iGyneFirstRegistrationStep.py (4) is the initial registration step. Depending on the choice you made on the previous step, you can click on the bright markers in the image or let the automatic registration find them for you (requires the CLI module called Hough Transform). 

- iGyneSecondRegistrationStep.py (5) is the refined applicator registration step. It offers fully automated computation to complete manual parameterization if needed. Thus, several segmentation methods are available to segment the obturator, and the registration parameters can be tweaked. By default, the most efficient parameters are chosen and all steps of the refined registration are computed successively. Evaluation functions have also been integrated to allow developers to measure time and accuracy of the chosen methods and parameters. Beside the control interface, 2D views display cross sections of the applicator in axial, sagital and coronal planes giving the user a visual characterization of the registration state.

- iGyneNeedlePlanningStep.py (6) let you insert "virtual needles" and visualize their trajectory in the 2D/3D viewer. You can tweak the color and the length of the needles.

- iGyneNeedleSegmentationStep.py (7) is the "keystone" of iGyne. Start by clicking on "Start Giving Needle Tips" and at each click in the 2D axial viewer, a needle will be segmented. You can display, delete the needles individually or all together. You can also differentiate the different insertion steps and separate each group of needles. A table shows some parameters of the caculated needles. If a registration has been done previously, it will assign to each needle the most probable label. It is also possible to tweak the needle segmentation parameters.
