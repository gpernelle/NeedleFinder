from __future__ import division
from __main__ import qt, ctk

class NFStep( ctk.ctkWorkflowWidgetStep ) :

  def __init__( self, stepid ):
    self.initialize( stepid )
    self.procedure = None

  def setWorkflow( self, workflow ):
    '''
    '''
    self.__workflow = workflow

  def setParameterNode(self, parameterNode):
    '''
    Keep the pointer to the parameter node for each step
    '''
    self.__parameterNode = parameterNode

  def setMRMLManager( self, mrmlManager ):
    self.__mrmlManager = mrmlManager

  def setLogic( self, logic ):
    self.__logic = logic

  def mrmlManager( self ):
    return self.__mrmlManager

  def logic( self ):
    return self.__logic


  def workflow( self ):
    return self.__workflow

  def parameterNode(self):
    return self.__parameterNode

  def getBoldFont( self ):
    '''
    '''
    boldFont = qt.QFont( "Sans Serif", 12, qt.QFont.Bold )
    return boldFont

  def createUserInterface( self ):
    self.__layout = qt.QFormLayout( self )
    self.__layout.setVerticalSpacing( 5 )

    # add empty row
    self.__layout.addRow( "", qt.QWidget() )
    # add empty row
    self.__layout.addRow( "", qt.QWidget() )

    return self.__layout

  def onEntry( self, comingFrom, transitionType ):
    comingFromId = "None"
    if comingFrom: comingFromId = comingFrom.id()
    #print "-> onEntry - current [%s] - comingFrom [%s]" % ( self.id(), comingFromId )
    super( NFStep, self ).onEntry( comingFrom, transitionType )

  def onExit( self, goingTo, transitionType ):
    goingToId = "None"
    if goingTo: goingToId = goingTo.id()
    #print "-> onExit - current [%s] - goingTo [%s]" % ( self.id(), goingToId )
    super( NFStep, self ).onExit( goingTo, transitionType )

  def validate( self, desiredBranchId ):
    return
    #print "-> validate %s" % self.id()

  def validationSucceeded( self, desiredBranchId ):
    '''
    '''
    super( NFStep, self ).validate( True, desiredBranchId )

  def validationFailed( self, desiredBranchId, messageTitle='Error', messageText='There was an unknown error. See the console output for more details!' ):
    '''
    '''
    messageBox = qt.QMessageBox.warning( self, messageTitle, messageText )
    super( NFStep, self ).validate( False, desiredBranchId )

  def setLabels(self):
    '''
    set the list of labels
    '''
    self.option = {0:'Ba',
       1:'Bb',
       2:'Bc',
       3:'Bd',
       4:'Be',
       5:'Bf',
       6:'Bg',
       7:'Bh',
       8:'Bi',
       9:'Bj',
       10:'Bk',
       11:'Bl',
       12:'Ca',
       13:'Cb',
       14:'Cc',
       15:'Cd',
       16:'Ce',
       17:'Cf',
       18:'Cg',
       19:'Ch',
       20:'Ci',
       21:'Cj',
       22:'Ck',
       23:'Cl',
       24:'Cm',
       25:'Cn',
       26:'Co',
       27:'Cp',
       28:'Cq',
       29:'Cr',
       30:'Da',
       31:'Db',
       32:'Dc',
       33:'Dd',
       34:'De',
       35:'Df',
       36:'Dg',
       37:'Dh',
       38:'Di',
       39:'Dj',
       40:'Ea',
       41:'Eb',
       42:'Ec',
       43:'Ed',
       44:'Ee',
       45:'Ef',
       46:'Eg',
       47:'Eh',
       48:'Aa',
       49:'Ab',
       50:'Ac',
       51:'Ad',
       52:'Ae',
       53:'Af',
       54:'Iu', 
       55:'Fa',
       56:'Fb',
       57:'Fc',
       58:'Fd',
       59:'Fe',
       60:'Ff',
       61:'Fg',
       62:'Fh',
       63:'--'}

    return self.option
 
  def setColors255(self):
    self.color255= [[0,0,0] for i in range(205)]
    self.color255[0]=[221,108,158]
    self.color255[1]=[128,174,128]
    self.color255[2]=[241,214,145]
    self.color255[3]=[177,122,101]
    self.color255[4]=[111,184,210]
    self.color255[5]=[216,101,79]
    self.color255[6]=[221,130,101]
    self.color255[7]=[144,238,144]
    self.color255[8]=[192,104,88]
    self.color255[9]=[220,245,20]
    self.color255[10]=[78,63,0]
    self.color255[11]=[255,250,220]
    self.color255[12]=[230,220,70]
    self.color255[13]=[200,200,235]
    self.color255[14]=[250,250,210]
    self.color255[15]=[244,214,49]
    self.color255[16]=[0,151,206]
    self.color255[17]=[183,156,220]
    self.color255[18]=[183,214,211]
    self.color255[19]=[152,189,207]
    self.color255[20]=[178,212,242]
    self.color255[21]=[68,172,100]
    self.color255[22]=[111,197,131]
    self.color255[23]=[85,188,255]
    self.color255[24]=[0,145,30]
    self.color255[25]=[214,230,130]
    self.color255[26]=[218,255,255]
    self.color255[27]=[170,250,250]
    self.color255[28]=[140,224,228]
    self.color255[29]=[188,65,28]
    self.color255[30]=[216,191,216]
    self.color255[31]=[145,60,66]
    self.color255[32]=[150,98,83]
    self.color255[33]=[250,250,225]
    self.color255[34]=[200,200,215]
    self.color255[35]=[68,131,98]
    self.color255[36]=[83,146,164]
    self.color255[37]=[162,115,105]
    self.color255[38]=[141,93,137]
    self.color255[39]=[182,166,110]
    self.color255[40]=[188,135,166]
    self.color255[41]=[154,150,201]
    self.color255[42]=[177,140,190]
    self.color255[43]=[30,111,85]
    self.color255[44]=[210,157,166]
    self.color255[45]=[48,129,126]
    self.color255[46]=[98,153,112]
    self.color255[47]=[69,110,53]
    self.color255[48]=[166,113,137]
    self.color255[49]=[122,101,38]
    self.color255[50]=[253,135,192]
    self.color255[51]=[145,92,109]
    self.color255[52]=[46,101,131]
    self.color255[53]=[0,108,112]
    self.color255[54]=[127,150,88]
    self.color255[55]=[159,116,163]
    self.color255[56]=[125,102,154]
    self.color255[57]=[106,174,155]
    self.color255[58]=[154,146,83]
    self.color255[59]=[126,126,55]
    self.color255[60]=[201,160,133]
    self.color255[61]=[78,152,141]
    self.color255[62]=[174,140,103]
    self.color255[63]=[139,126,177]
    self.color255[64]=[148,120,72]
    self.color255[65]=[186,135,135]
    self.color255[66]=[99,106,24]
    self.color255[67]=[156,171,108]
    self.color255[68]=[64,123,147]
    self.color255[69]=[138,95,74]
    self.color255[70]=[97,113,158]
    self.color255[71]=[126,161,197]
    self.color255[72]=[194,195,164]
    self.color255[73]=[88,106,215]
    self.color255[74]=[82,174,128]
    self.color255[75]=[57,157,110]
    self.color255[76]=[60,143,83]
    self.color255[77]=[92,162,109]
    self.color255[78]=[255,244,209]
    self.color255[79]=[201,121,77]
    self.color255[80]=[70,163,117]
    self.color255[81]=[188,91,95]
    self.color255[82]=[166,84,94]
    self.color255[83]=[182,105,107]
    self.color255[84]=[229,147,118]
    self.color255[85]=[174,122,90]
    self.color255[86]=[201,112,73]
    self.color255[87]=[194,142,0]
    self.color255[88]=[241,213,144]
    self.color255[89]=[203,179,77]
    self.color255[90]=[229,204,109]
    self.color255[91]=[255,243,152]
    self.color255[92]=[209,185,85]
    self.color255[93]=[248,223,131]
    self.color255[94]=[255,230,138]
    self.color255[95]=[196,172,68]
    self.color255[96]=[255,255,167]
    self.color255[97]=[255,250,160]
    self.color255[98]=[255,237,145]
    self.color255[99]=[242,217,123]
    self.color255[100]=[222,198,101]
    self.color255[101]=[213,124,109]
    self.color255[102]=[184,105,108]
    self.color255[103]=[150,208,243]
    self.color255[104]=[62,162,114]
    self.color255[105]=[242,206,142]
    self.color255[106]=[250,210,139]
    self.color255[107]=[255,255,207]
    self.color255[108]=[182,228,255]
    self.color255[109]=[175,216,244]
    self.color255[110]=[197,165,145]
    self.color255[111]=[172,138,115]
    self.color255[112]=[202,164,140]
    self.color255[113]=[224,186,162]
    self.color255[114]=[255,245,217]
    self.color255[115]=[206,110,84]
    self.color255[116]=[210,115,89]
    self.color255[117]=[203,108,81]
    self.color255[118]=[233,138,112]
    self.color255[119]=[195,100,73]
    self.color255[120]=[181,85,57]
    self.color255[121]=[152,55,13]
    self.color255[122]=[159,63,27]
    self.color255[123]=[166,70,38]
    self.color255[124]=[218,123,97]
    self.color255[125]=[225,130,104]
    self.color255[126]=[224,97,76]
    self.color255[127]=[184,122,154]
    self.color255[128]=[211,171,143]
    self.color255[129]=[47,150,103]
    self.color255[130]=[173,121,88]
    self.color255[131]=[188,95,76]
    self.color255[132]=[255,239,172]
    self.color255[133]=[226,202,134]
    self.color255[134]=[253,232,158]
    self.color255[135]=[244,217,154]
    self.color255[136]=[205,179,108]
    self.color255[137]=[186,124,161]
    self.color255[138]=[255,255,220]
    self.color255[139]=[234,234,194]
    self.color255[140]=[204,142,178]
    self.color255[141]=[180,119,153]
    self.color255[142]=[216,132,105]
    self.color255[143]=[255,253,229]
    self.color255[144]=[205,167,142]
    self.color255[145]=[204,168,143]
    self.color255[146]=[255,224,199]
    self.color255[147]=[139,150,98]
    self.color255[148]=[249,180,111]
    self.color255[149]=[157,108,162]
    self.color255[150]=[203,136,116]
    self.color255[151]=[185,102,83]
    self.color255[152]=[247,182,164]
    self.color255[153]=[222,154,132]
    self.color255[154]=[124,186,223]
    self.color255[155]=[249,186,150]
    self.color255[156]=[244,170,147]
    self.color255[157]=[255,181,158]
    self.color255[158]=[255,190,165]
    self.color255[159]=[227,153,130]
    self.color255[160]=[213,141,113]
    self.color255[161]=[193,123,103]
    self.color255[162]=[216,146,127]
    self.color255[163]=[230,158,140]
    self.color255[164]=[245,172,147]
    self.color255[165]=[241,172,151]
    self.color255[166]=[177,124,92]
    self.color255[167]=[171,85,68]
    self.color255[168]=[217,198,131]
    self.color255[169]=[212,188,102]
    self.color255[170]=[185,135,134]
    self.color255[171]=[198,175,125]
    self.color255[172]=[194,98,79]
    self.color255[173]=[255,238,170]
    self.color255[174]=[206,111,93]
    self.color255[175]=[216,186,0]
    self.color255[176]=[255,226,77]
    self.color255[177]=[255,243,106]
    self.color255[178]=[255,234,92]
    self.color255[179]=[240,210,35]
    self.color255[180]=[224,194,0]
    self.color255[181]=[213,99,79]
    self.color255[182]=[217,102,81]
    self.color255[183]=[0,147,202]
    self.color255[184]=[0,122,171]
    self.color255[185]=[186,77,64]
    self.color255[186]=[240,255,30]
    self.color255[187]=[185,232,61]
    self.color255[188]=[0,226,255]
    self.color255[189]=[251,159,255]
    self.color255[190]=[230,169,29]
    self.color255[191]=[0,194,113]
    self.color255[192]=[104,160,249]
    self.color255[193]=[221,108,158]
    self.color255[194]=[137,142,0]
    self.color255[195]=[230,70,0]
    self.color255[196]=[0,147,0]
    self.color255[197]=[0,147,248]
    self.color255[198]=[231,0,206]
    self.color255[199]=[129,78,0]
    self.color255[200]=[0,116,0]
    self.color255[201]=[0,0,255]
    self.color255[202]=[157,0,0]
    self.color255[203]=[100,100,130]
    self.color255[204]=[205,205,100]
    
    return self.color255

  def setColors(self):
    self.color= [[0,0,0] for i in range(205)]
    self.color255= self.setColors255()
    for i in range(205):
      for j in range(3):
        self.color[i][j] = self.color255[i][j]/(255)

    return self.color

  def setHolesCoordinates(self):
    self.p = [[0 for j in range(63)] for j in range(3)]
    self.p[0][0]=35
    self.p[1][0]=34
    self.p[0][1]=25
    self.p[1][1]=36.679
    self.p[0][2]=17.679
    self.p[1][2]=44
    self.p[0][3]=15
    self.p[1][3]=54
    self.p[0][4]=17.679
    self.p[1][4]=64
    self.p[0][5]=25
    self.p[1][5]=71.321
    self.p[0][6]=35
    self.p[1][6]=74
    self.p[0][7]=45
    self.p[1][7]=71.321
    self.p[0][8]=52.321
    self.p[1][8]=64
    self.p[0][9]=55
    self.p[1][9]=54
    self.p[0][10]=52.321
    self.p[1][10]=44
    self.p[0][11]=45
    self.p[1][11]=36.679
    self.p[0][12]=29.791
    self.p[1][12]=24.456
    self.p[0][13]=20
    self.p[1][13]=28.019
    self.p[0][14]=12.019
    self.p[1][14]=34.716
    self.p[0][15]=6.809
    self.p[1][15]=43.739
    self.p[0][16]=5
    self.p[1][16]=54
    self.p[0][17]=6.809
    self.p[1][17]=64.261
    self.p[0][18]=12.019
    self.p[1][18]=73.284
    self.p[0][19]=20
    self.p[1][19]=79.981
    self.p[0][20]=29.791
    self.p[1][20]=83.544
    self.p[0][21]=40.209
    self.p[1][21]=83.544
    self.p[0][22]=50
    self.p[1][22]=79.981
    self.p[0][23]=57.981
    self.p[1][23]=73.284
    self.p[0][24]=63.191
    self.p[1][24]=64.262
    self.p[0][25]=65
    self.p[1][25]=54
    self.p[0][26]=63.191
    self.p[1][26]=43.739
    self.p[0][27]=57.981
    self.p[1][27]=34.716
    self.p[0][28]=50
    self.p[1][28]=28.019
    self.p[0][29]=40.209
    self.p[1][29]=24.456
    self.p[0][30]=35
    self.p[1][30]=14
    self.p[0][31]=24.647
    self.p[1][31]=15.363
    self.p[0][32]=15
    self.p[1][32]=19.359
    self.p[0][33]=15
    self.p[1][33]=88.641
    self.p[0][34]=24.647
    self.p[1][34]=92.637
    self.p[0][35]=35
    self.p[1][35]=94
    self.p[0][36]=45.353
    self.p[1][36]=92.637
    self.p[0][37]=55
    self.p[1][37]=88.641
    self.p[0][38]=55
    self.p[1][38]=19.359
    self.p[0][39]=45.353
    self.p[1][39]=15.363
    self.p[0][40]=30.642
    self.p[1][40]=4.19
    self.p[0][41]=22.059
    self.p[1][41]=5.704
    self.p[0][42]=22.059
    self.p[1][42]=102.296
    self.p[0][43]=30.642
    self.p[1][43]=103.81
    self.p[0][44]=39.358
    self.p[1][44]=103.81
    self.p[0][45]=47.941
    self.p[1][45]=102.296
    self.p[0][46]=47.941
    self.p[1][46]=5.704
    self.p[0][47]=39.358
    self.p[1][47]=4.19
    self.p[0][48]=29.7
    self.p[1][48]=44.82
    self.p[0][49]=24.4
    self.p[1][49]=54
    self.p[0][50]=29.7
    self.p[1][50]=63.18
    self.p[0][51]=40.3
    self.p[1][51]=63.18
    self.p[0][52]=45.6
    self.p[1][52]=54
    self.p[0][53]=40.3
    self.p[1][53]=44.82
    self.p[0][54]=35
    self.p[1][54]=54
    self.p[0][55]=9
    self.p[1][55]=12
    self.p[0][56]=5
    self.p[1][56]=18
    self.p[0][57]=5
    self.p[1][57]=90
    self.p[0][58]=9
    self.p[1][58]=96
    self.p[0][59]=61
    self.p[1][59]=96
    self.p[0][60]=65
    self.p[1][60]=90
    self.p[0][61]=65
    self.p[1][61]=18
    self.p[0][62]=61
    self.p[1][62]=12

    return self.p
