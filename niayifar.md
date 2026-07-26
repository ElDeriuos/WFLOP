energies
Article
Analytical Modeling of Wind Farms:
A New Approach for Power Prediction
AminNiayifar1,2andFernandoPorté-Agel1,*
1 WindEngineeringandRenewableEnergyLaboratory(WIRE),ÉcolePolytechniqueFédéraledeLausanne(EPFL),
EPFL-ENAC-IIE-WIRE,1015Lausanne,Switzerland;amin.niayifar@epfl.ch
2 StreamBiofilmandEcosystemResearchLaboratory(SBER),ÉcolePolytechniqueFédéraledeLausanne(EPFL),
EPFL-ENAC-IIE-SBER,1015Lausanne,Switzerland
* Correspondence:fernando.porte-agel@epfl.ch;Tel.:+41-21-693-6138
AcademicEditor:FredeBlaabjerg
Received:11April2016;Accepted:31August2016;Published:15September2016
Abstract: Windfarmpowerproductionisknowntobestronglyaffectedbyturbinewakeeffects.
Thepurposeofthisstudyistodevelopandtestanewanalyticalmodelforthepredictionofwind
turbinewakesandtheassociatedpowerlossesinwindfarms. Thenewmodelisanextensionof
theonerecentlyproposedbyBastankhahandPorté-Agelforthewakeofstand-alonewindturbines.
Itsatisfiestheconservationofmassandmomentumandassumesaself-similarGaussianshapeofthe
velocitydeficit. Thelocalwakegrowthrateisestimatedbasedonthelocalstreamwiseturbulence
intensity. Superpositionofvelocitydeficitsisusedtomodeltheinteractionofthemultiplewakes.
Furthermore, the power production from the wind turbines is calculated using the power curve.
Theperformanceofthenewanalyticalwindfarmmodelisvalidatedagainstpowermeasurements
and large-eddy simulation (LES) data from the Horns Rev wind farm for a wide range of wind
directions, corresponding to a variety of full-wake and partial-wake conditions. A reasonable
agreementisfoundbetweentheproposedanalyticalmodel,LESdata,andpowermeasurements.
Compared with a commonly used wind farm wake model, the new model shows a significant
improvementinthepredictionofwindfarmpower.
Keywords: analytical model; Gaussian velocity deficit; turbulence intensity; velocity deficit
superposition;wakegrowthrate;windfarmpowerproduction
1. Introduction
Renewableenergiesplayanincreasinglyimportantroleintheglobalenergymarketassourcesof
sustainableandcleanenergy. Specifically,windenergyiswitnessingcontinuousgrowthatanaverage
annualrateofapproximately25%andcurrentlycontributestomorethan2.6%ofelectricitygeneration
worldwide. This contribution is expected to increase to 18% of the world’s electricity generation
by2050[1].
Powerproductionfromwindfarmsissignificantlyaffectedbywindturbinewakes. Thispower
loss can be up to 25% of the total power output [2]. For this reason, the accurate prediction of
turbine wakes is imperative to minimize power losses and, thus, increase the overall efficiency of
wind farms. Turbine wake effects have been investigated in numerous experimental, numerical,
and analytical studies. Recent advances in turbulence-resolving computational fluid dynamics
methods,suchaslarge-eddysimulation(LES)andcutting-edgeexperimentaltechniques,haveallowed
detailedcharacterizationofwindturbinewakeflows. Althoughbothexperimentalandnumerical
approacheshavethepotentialofprovidingaccurateresults,thesimplicityandlowcomputationalcost
associatedwithanalyticalmodelsmakethemappealingforwindfarmoptimizationpurposes[3,4].
Forthatreason,analyticalmodelingofwindfarmshasbeenandcontinuestobeanimportanttopic
Energies2016,9,741;doi:10.3390/en9090741 www.mdpi.com/journal/energies

| Energies2016,9,741 |     |     |     |     |     |     |     |     | 2of13 |
| ------------------ | --- | --- | --- | --- | --- | --- | --- | --- | ----- |
ofresearchinthefieldofwindenergy. Analyticalwindfarmmodelscanbedividedintotwomain
types: Kinematicmodels(e.g.,[5,6])anddistributedroughnessmodels(e.g.,[7–9]). Kinematicmodels
considereachturbinewakeindividuallyandapplysuperpositionprinciplestoaddresstheinteraction
ofneighboringwakes.Indistributedroughnessmodels,turbinesactasdistributedroughnesselements
inwhichtheambientatmosphericflowismodified. Furthermore,therearesomemodelsthatcombine
kinematicmodelswithdistributedroughnessmodels(e.g.,[10,11]). Inthepresentstudy,wepropose
anewwindfarmanalyticalmodel,whichisatypeofkinematicmodel,topredicttheperformance
of wind farms of arbitrary size and layout. Although several analytical wind farm models have
been developed to estimate the power generated from wind turbines, there are still some critical
issuesrelatedtothemodelingofthevelocitydeficitandthevelocitydeficitsuperposition(duetothe
interactionofmultiplewakes)thatneedtobeaddressedtoincreasetheaccuracyandrobustnessof
thesemodels.
Several analytical wake models have been developed to estimate the wake flow inside wind
farms[5,12–15]. OneofthemostcommonlyusedwakemodelsistheoneproposedbyJensen[6,12].
Thismodel,whichhasbeenextensivelyusedintheliterature(e.g.,[16])andincommercialsoftware
(e.g.,[17–21]),considersatop-hatshapeforthenormalizedvelocitydeficitandisdefinedas:
|     | ∆U  | U∞−U | (cid:16) |           | (cid:17) (cid:18) |     | (cid:19)2 |     |     |
| --- | --- | ---- | -------- | --------- | ----------------- | --- | --------- | --- | --- |
|     |     |      | w        | (cid:112) |                   | 2k  | wake x    |     |     |
|     |     | =    | = 1−     | 1−C       | /                 | 1+  | ,         |     | (1) |
|     | U∞  | U∞   |          |           | T                 |     | d         |     |     |
0
whereU∞istheundisturbedvelocity,U w isthewakevelocity,C T isthethrustcoefficientoftheturbine,
k isthewakespreadingparameter,d isthewindturbinediameter,andxisthedistancebehind
| wake |     |     | 0   |     |     |     |     |     |     |
| ---- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
theturbine. Itshouldbenotedthatthismodelwasderivedusingonlymassconservation[15].
In a later study, Frandsen et al. [14] also assumed a top-hat shape for the velocity deficit and
appliedconservationofmassandmomentumtoacontrolvolumearoundtheturbinetoderivethe
followingmodel:
|     |     |     | (cid:32) | (cid:115) |       | (cid:33) |     |     |     |
| --- | --- | --- | -------- | --------- | ----- | -------- | --- | --- | --- |
|     |     |     | ∆U       |           | A     |          |     |     |     |
|     |     |     | 1        |           | 0     |          |     |     |     |
|     |     |     | =        | 1−        | 1−2 C | ,        |     |     | (2) |
|     |     |     | U∞ 2     |           | A     | T        |     |     |     |
w
where A denotes the circular area swept by the wind turbine blades and A represents the
| 0   |     |     |     |     |     |     |     | w   |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
cross-sectionalareaofthewake. Despitethewideuseoftheseturbinewakemodelsintheliterature
andcommercialsoftware,theunrealisticassumptionofatop-hatvelocitydeficitresultsinatendency
forthesemodelstooverestimatepowerpredictioninthefull-wakeconditionandunderestimatepower
predictioninthepartial-wakecondition.
Thenormalizedvelocitydeficitintheturbinewakeshasbeenobservedtofollowaself-similar
Gaussianprofileinseveralexperimentalandnumericalresearchstudies(e.g.,[22–25]). Inagreement
with this observation, a recently developed Gaussian wake model by Bastankhah and Porté-Agel
was found to provide substantially better results in both full-wake and partial-wake conditions
whencomparedtotop-hatwakemodels[15]. Intheiranalyticalwakemodel,massandmomentum
conservationisappliedtoacontrolvolumearoundoneturbinewhereaself-similarGaussianprofileis
assumedforthevelocitydeficittoderivethefollowingequationforthenormalizedvelocitydeficit:
(cid:32) (cid:115) (cid:33) (cid:32) (cid:40)(cid:18) (cid:19)2 (cid:18) (cid:19)2 (cid:41)(cid:33)
| ∆U   |     | C   |      |     | 1   |     | z−z | y   |     |
| ---- | --- | --- | ---- | --- | --- | --- | --- | --- | --- |
| = 1− | 1−  | T   | ×exp | −   |     |     | h + |     |     |
, (3)
| U∞  | 8(k∗x/d | +ε)2 |     | 2(k∗x/d | +ε)2 |     | d   | d   |     |
| --- | ------- | ---- | --- | ------- | ---- | --- | --- | --- | --- |
|     |         | 0    |     |         | 0    |     | 0   | 0   |     |
wherex,y,andzarestreamwise,spanwise,andverticalcoordinates,respectively,andz isthehub
h
k∗
height level. denotes the wake growth rate which is a function of thrust coefficient and local
streamwiseturbulenceintensity[15]. Theyalsoproposedthefollowingexpressionforε:
(cid:112)
|                      |     |                      |     | ε =0.2 | β,  |     |     |     | (4) |
| -------------------- | --- | -------------------- | --- | ------ | --- | --- | --- | --- | --- |
| whereβisafunctionofC |     | andcanbeexpressedas: |     |        |     |     |     |     |     |
T

Energies2016,9,741 3of13
√
| 11+   | 1−C         |     |     |
| ----- | ----------- | --- | --- |
| β = √ | T , C <0.9. |     | (5) |
T
| 2 1−C |     |     |     |
| ----- | --- | --- | --- |
T
Dependingonthewinddirection,windturbinesinsidewindfarmsareoftenexposedtomultiple
wakesfromseveralupstreamwindturbines. Therefore,analyticalwindfarmwakemodelsneedto
accountforthecumulativewakeflowsthatareformedbytheinteractionofmultiplewakes. Toachieve
that,windfarmmodelspredictcumulativewakeeffectsbyapplyingstand-alonewakemodelstoeach
individualturbine,togetherwithsuperpositionprinciplestorepresentthecombinedeffectsofmultiple
overlappingwakes. Lissaman[5]proposedamodelforthecumulativevelocitydeficitbasedonthe
linearsuperpositionofvelocitydeficits. Thismodelconsidersananalogybetweenthepoint-source
pollutantdispersion(e.g.,fromsmokestacks)andthewindturbinewakeexpansionintheatmospheric
boundarylayerandisdefinedas:
∑
| U = U∞− | (U∞− U | ),  | (5) |
| ------- | ------ | --- | --- |
| i       |        | ki  |     |
k
where U is the velocity at the turbine i and U is the wake velocity of the turbine k at turbine i
i ki
consideringonlythoseturbineswhosewakesinteractwithturbinei. Katicetal.[6]lateronusedthe
superpositionofenergydeficits,insteadofvelocitydeficits,tomodeltheinteractionofmultiplewakes
asfollows:
(cid:114)
|         | ∑      | )2  |     |
| ------- | ------ | --- | --- |
| U = U∞− | (U∞− U | ,   | (6) |
| i       |        | ki  |     |
k
whereforeachindividualwakeinsidethewindfarm,thekineticenergydeficitofmultiplewakes
is assumed to be equal to the sum of the energy deficits from the relevant upwind turbines.
Voutsinasetal.[13]followedthesameapproachasKaticetal.[6],buttoestimatetheenergydeficitof
eachwake,theyconsideredthedifferencebetweentheinflowvelocityattheturbineandthewake
velocityasfollows:
(cid:114) ∑
| U = U∞− | (U − U | )2 . | (7) |
| ------- | ------ | ---- | --- |
| i       | k      | ki   |     |
k
Inwindfarms,turbinewakeflowsleadtoasubstantialincreaseinthelevelofturbulenceintensity
withrespecttotheturbulenceleveloftheincomingatmosphericboundarylayerflow. Thiseffecthas
beenobservedinseveralnumericalandexperimentalstudies(e.g.,[26–29]). Furthermore,somerecent
research studies have shown that the wake growth rate increases as the turbulence intensity level
increases(e.g.,[15]),yetmostofthecommonanalyticalwindfarmmodelsassumeaconstantwake
growthrateinsideawindfarm. Sincetheconstantwakegrowthrateassumptionislikelyunrealistic,
weproposeanempiricalequationforthelocalwakegrowthratethatisbasedonthelocalstreamwise
turbulenceintensitytoconsidertheturbulenceeffectinwindfarms. Severalresearchstudieshave
attemptedtomodeltheaddedstreamwiseturbulenceintensityinsidewindfarms[30–32]. Ingeneral,
thesemodelsusethethrustcoefficientoftheturbinesandtheambientturbulenceintensitytoestimate
theaddedstreamwiseturbulenceintensityatthewindturbinehubheightasfollows:
(cid:113)
| I+ = | I 2 −I 2, |     | (8) |
| ---- | --------- | --- | --- |
w ake 0
whereI isthestreamwiseturbulenceintensityinthewakeandI istheambientturbulenceintensity.
wake 0
QuartonandAinsile[30]proposedthefollowingempiricalexpressiontopredicttheaddedstreamwise
turbulenceintensitygeneratedbyawindturbine:
| = 0.7I  | 0.68(x/x )−0.57 |     |     |
| ------- | --------------- | --- | --- |
| I+ 4.8C | n               | ,   | (9) |
T 0
wherex n isthelengthofthenear-wakeregion,whichisdefinedas[33]:

| Energies2016,9,741 |     |     |     |         |          |          |         |     |               |     | 4of13 |
| ------------------ | --- | --- | --- | ------- | -------- | -------- | ------- | --- | ------------- | --- | ----- |
|                    |     |     |     | √       |          |          | √       |     |               |     |       |
|                    |     |     |     |         |          | (cid:0)  |         |     | (cid:1)       |     |       |
|                    |     |     |     | 0.214   | + 0.144m | 1        | − 0.134 | +   | 0.124m        | r   |       |
|                    |     |     | =   | √       |          |          | √       |     |               | 0   |       |
|                    |     |     | x n | (cid:0) |          |          | (cid:1) |     |               | ,   | (10)  |
|                    |     |     |     | 1 −     | 0.214    | + 0.144m | 0.134   | +   | 0.124m(dr/dx) |     |       |
(cid:113)
m+1,anddr/dxisdefinedbythefollowingexpression:
| wherem | =                 | √ 1 ,r | = (d    | /2)      |           |                    |          |           |                    |                         |      |
| ------ | ----------------- | ------ | ------- | -------- | --------- | ------------------ | -------- | --------- | ------------------ | ----------------------- | ---- |
|        |                   | 1−CT   | 0       | 0        | 2         |                    |          |           |                    |                         |      |
|        |                   |        |         |          | (cid:115) | (cid:18) (cid:19)2 | (cid:18) | (cid:19)2 | (cid:18) (cid:19)2 |                         |      |
|        |                   |        |         |          |           | dr                 | dr       |           | dr                 |                         |      |
|        |                   |        |         |          | =         |                    | +        | +         |                    |                         |      |
|        |                   |        |         | dr/dx    |           |                    |          |           |                    | ,                       | (11) |
|        |                   |        |         |          |           | dx                 | dx       |           | dx                 |                         |      |
|        |                   |        |         |          |           |                    | a        | m         |                    | λ                       |      |
|        | (cid:16) (cid:17) |        |         | (cid:16) | (cid:17)  |                    | √        | (cid:16)  | (cid:17)           |                         |      |
|        | dr                | =      | +0.005, | dr       | =         | (1−m)              | 1.49+m   |           | dr =               |                         |      |
| where  |                   | 2.5I   | 0       |          |           |                    |          | ,and      |                    | 0.012Bλ. Bisthenumberof |      |
|        | dx                | a      |         | dx       | m         | 9.76(1+m)          |          |           | dx λ               |                         |      |
bladesandλisthetipspeedratio. Later,HassanandHassan[31]suggestedthefollowingexpression
fortheaddedstreamwiseturbulenceintensity:
|     |     |     |     |     | I+ = | 5.7C 0.7I | 0.68(x/x | )−0.96 | .   |     | (13) |
| --- | --- | --- | --- | --- | ---- | --------- | -------- | ------ | --- | --- | ---- |
|     |     |     |     |     |      | T         | 0        | n      |     |     |      |
Based on a numerical study, Crespo and Hernandez [32] suggested the following empirical
equationfortheparameterranges5 < x/d <15,0.07 < I < 0.14,and0.1 < a <0.4,whereais
|     |     |     |     |     |     | 0   |     | u   |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
theinductionfactor:
|     |     |     |     |     | I+ = 0.73a0.8325I |     | 0.0325(x/d)−0.32 |     | .   |     | (14) |
| --- | --- | --- | --- | --- | ----------------- | --- | ---------------- | --- | --- | --- | ---- |
0
Thispaperisstructuredasfollows: Theproposedanalyticalwindfarmwakemodelispresented
inSection2. Adescriptionofthecasestudy(theHornsRevwindfarm)isthengiveninSection3.
InSection4,theresultsobtainedwiththenewanalyticalwindfarmmodelarediscussedandcompared
withpowermeasurementsandwithresultsfromLESandacommonly-usedanalyticalwindfarm
model. Finally,asummaryandconclusionareprovidedinSection5.
2. DescriptionoftheNewAnalyticalWindFarmModel
The proposed analytical wind farm model uses the self-similar Gaussian model, recently
developedbyBastankhahandPorté-Agel[15],togetherwiththeassumptionofsuperpositionofthe
velocitydeficitforthecumulativewakeeffects. Next,detailsoftheformulationandimplementation
ofthenewwindfarmmodelaregiven.
2.1. AnalyticalModelfortheVelocityDeficit
The Gaussian wake model of Bastankhah and Porté-Agel [15] (Equations (3)–(5)) is applied
individually to each of the turbines in the wind farm. For single wakes, this model considers
aself-similarGaussiandistributionforthenormalizedvelocitydeficit,inwhichmassandmomentum
are conserved. In this study, the operating conditions of the wind turbines are within a range for
whichthethrustcoefficientisapproximatelyconstant(seeSection3). Forthisreason,wakegrowth
rateisassumedtobeonlyafunctionoflocalstreamwiseturbulenceintensity. Figure1showsthe
wakegrowthratebehindaV-80turbineobtainedfromLESforawiderangeofstreamwiseturbulence
intensitiesoftheincomingboundarylayerwindathubheightlevel[15]. Basedontheaforementioned
numericaldata, thefollowingempiricalexpressionisproposedtocalculatethegrowthrateofthe
< <0.15):
wakebehindeachturbinefortherangeofconditionsconsideredherein(0.065 I
|     |     |     |     |     | ∗   | =0.3837I+ |           |     |     |     |      |
| --- | --- | --- | --- | --- | --- | --------- | --------- | --- | --- | --- | ---- |
|     |     |     |     |     | k   |           | 0.003678, |     |     |     | (15) |
where I isthelocalstreamwiseturbulenceintensityimmediatelyupwindoftherotorcenter,whichis
estimated while neglecting any potential effect of that turbine on the upwind turbulence level.
The generalization of Equation (15) to include a wider range of turbine operation conditions and
inflowcharacteristicswillbethefocusofourfutureresearch.

Energies2016,9,741 5of13
Energies 2016, 9, 741 5 of 13
Figure 1. Wake growth rate for the V-80 turbine in boundary layer flow with different streamwise
Figure1. WakegrowthratefortheV-80turbineinboundarylayerflowwithdifferentstreamwise
turbulence intensities at hub height.
turbulenceintensitiesathubheight.
The interaction among multiple wakes is modeled by applying a new approach, which is based
Theinteractionamongmultiplewakesismodeledbyapplyinganewapproach,whichisbased
on the velocity deficit superposition principle. Previously, Lissaman [5] applied velocity deficit
on the velocity deficit superposition principle. Previously, Lissaman [5] applied velocity deficit
superposition that explicitly considers the difference between the undisturbed velocity and the wake
superpositionthatexplicitlyconsidersthedifferencebetweentheundisturbedvelocityandthewake
velocity. It should be noted that this method of wake superposition results in an overestimation of
velocity. Itshouldbenotedthatthismethodofwakesuperpositionresultsinanoverestimationofthe
the velocity deficit, specifically where there are several rows of wind turbines [3]. Here, instead, to
velocitydeficit,specificallywherethereareseveralrowsofwindturbines[3].Here,instead,toestimate
estimate the velocity deficit, we propose to calculate the difference between the inflow velocity at the
thevelocitydeficit,weproposetocalculatethedifferencebetweentheinflowvelocityattheturbine
turbine and the wake velocity as follows:
andthewakevelocityasfollows:
𝑈 = 𝑈 −∑(𝑈 − 𝑈 ) .
𝑖 ∞ ∑ 𝑘 𝑘𝑖 (16)
U
i
= U∞−
𝑘
(U
k
− U
ki
) . (16)
k
Similar to the single-wake model, it is vital that the wake superposition procedure conserves
massS aimndil amrotomtehnetusmin.g Llei-swsaamkaenm [o5]d ejul,stiitfiiesdv itthael ltihnaetatrh seuwpearkpeossuitpioenr poof stihtieo nwapkroesc.e dHuer earcgounesde rtvheast
mthaesres aisn danm aonmaleongtyu mbe.tLwiseseanm taunrb[i5n]ej uwstaikfieesd atnhde lpinoellaurtsiounp eprlpuomsietsio, nwohfotshee Gwaauksessia.nH ceoanrcgeunetdratthioant
tdhiestrreibisutaionna ncaanlo bgey sbueptwereimenptousrebdi naes wa arkeseuslat nodf tphoel lluintieoanriptyl uomf eths,e wphroocseessG. aIuns tshiaen sacomnec ewnatrya ttihoant
dpiosltlruitbauntti osnupcearnpobseitsiuopn ecroimnspeorvseeds masasas,r ethsue lltinoefatrhizeeldin meaormityenotfutmhe dpefrioccite siss .coInnstehrevesdam bey wapapylythinagt
psuoplleurtpaonstistiuopne orpf ovseiltoiocintyc odnesfiecrivt.e smass,thelinearizedmomentumdeficitisconservedbyapplying
superpositionofvelocitydeficit.
2.2. Turbulence Intensity Model
2.2. TurbulenceIntensityModel
For the local streamwise turbulence intensity, we propose to use a top-hat distribution with a
For the local streamwise turbulence intensity, we propose to use a top-hat distribution with
wake diameter of 4𝜎, which has been derived empirically based on LES data [26], where 𝜎 denotes
awakediameterof4σ,whichhasbeenderivedempiricallybasedonLESdata[26],whereσdenotes
the standard deviation of the Gaussian-like velocity deficit. It is defined [15] as:
thestandarddeviationoftheGaussian-likevelocitydeficit. Itisdefined[15]as:
𝜎⁄𝑑 = 𝑘∗𝑥⁄𝑑 +𝜀 . (17)
0 0
σ/d = k ∗ x/d +ε. (17)
The enhancement of streamwise turbul0ence inten0sity for individual turbines is calculated from
Equation (14). Then, the local streamwise turbulence intensity is found using Equation (8).
Theenhancementofstreamwiseturbulenceintensityforindividualturbinesiscalculatedfrom
Several numerical and experimental studies have shown that the level of turbulence intensity
Equation(14). Then,thelocalstreamwiseturbulenceintensityisfoundusingEquation(8).
increases inside a wind farm. Furthermore, the level of turbulence intensity has been observed to
Severalnumericalandexperimentalstudieshaveshownthatthelevelofturbulenceintensity
quickly reach an equilibrium after 2–3 rows of wind turbines [26,34]. A previous study by Frandsen
increasesinsideawindfarm. Furthermore, thelevelofturbulenceintensityhasbeenobservedto
and Thøgersen [35] has also shown that to predict the turbulence intensity in the wake of a given
quicklyreachanequilibriumafter2–3rowsofwindturbines[26,34]. ApreviousstudybyFrandsen
turbine, the only important effect is that of neighboring upstream turbines. In this respect, for every
and Thøgersen [35] has also shown that to predict the turbulence intensity in the wake of a given
turbine, we consider solely the added streamwise turbulence intensity caused by the nearest
turbine,theonlyimportanteffectisthatofneighboringupstreamturbines. Inthisrespect,forevery
upstream turbine whose wake has the most significant impact. It is defined as:
turbine,weconsidersolelytheaddedstreamwiseturbulenceintensitycausedbythenearestupstream
turbinewhosewakehasthemostsignificantimp𝐴a𝑤c4t. Itisdefinedas:
𝐼 + 𝑗 =max( 𝜋𝑑 2 𝐼 + 𝑘𝑗 ), (18)
0

Energies2016,9,741 6of13
(cid:18) (cid:19)
A 4
I+ =max w I+ , (18)
j πd 2 kj
0
Energies 2016, 9, 741 6 of 13
where I+
j
istheaddedstreamwiseturbulenceintensityattheturbinej, A
w
istheintersectionbetween
the wawkheer(eu s𝐼 +in 𝑗g isE tqhue aatdiodned( 1s7tr)e)aamnwdisteh teurrboutolerncaer einat,eannsidty Ia + t theis tuthrbeinaed d𝑗,e 𝐴d𝑤s tirse tahme winitseersetcutriobnu lence
kj
intensibteytwinedenu ctehde bwyakthe e(utusirnbgi nEequkaattiotnh e(1t7u)r) bainnde jt.he rotor area, and 𝐼
+ 𝑘𝑗
is the added streamwise
tuErnberugileesn 2c01e6 i, n9,t 7e4n1s ity induced by the turbine 𝑘 at the turbine 𝑗. 6 of 13
2.3. PowerPrediction
2.w3.h Peorew e𝐼r+ P 𝑗r eisd itchtieo na dded streamwise turbulence intensity at the turbine 𝑗, 𝐴 𝑤 is the intersection
Thbeetpwoewene rthceu wrvaek,e w(uhsiincgh Egqiuvaetsiotnh e(17p)o) wanedr tphreo rdoutocrt iaornea,a sanad f𝐼unc tiiso nthoe faidndceodm stirnegamwwiinsed speed,
The power curve, which gives the power production as a functi+o 𝑘n𝑗 of incoming wind speed, is
isusedttuorbpurleedniccet inthteenspitoyw inedrugceedn ebrya ttheed tubrybienaec h𝑘 taut rthbein tuer.bHineer e𝑗., thedataavailableforVestasV-80wind
used to predict the power generated by each turbine. Here, the data available for Vestas V-80 wind
turbinesisusedwhereafifthdegreepolynomialisfittedtothedata,asshowninFigure2.
turbines is used where a fifth degree polynomial is fitted to the data, as shown in Figure 2.
2.3. Power Prediction
The power curve, which gives the power production as a function of incoming wind speed, is
used to predict the power generated by each turbine. Here, the data available for Vestas V-80 wind
turbines is used where a fifth degree polynomial is fitted to the data, as shown in Figure 2.
Figure 2. Power curve of the V-80 wind turbine. Red circles correspond to the manufacturer’s data
Figure2.PowercurveoftheV-80windturbine.Redcirclescorrespondtothemanufacturer’sdataand
and the blue line represents a polynomial fit.
thebluelinerepresentsapolynomialfit.
3. Case Description
Figure 2. Power curve of the V-80 wind turbine. Red circles correspond to the manufacturer’s data
3. CaseDescription
Waned s tehlee cbtleude ltinhee rHeporersnesn tRs eav p oolfyfnsohmoriael wfiti. n d farm as a case study because LES flow and power
Wperesdeilceticotnesd [2t6h,e36H] aonrdn psoRweevr mofefasshuorermeewnitns d[17f,a3r7m] araes avaacilaasbeles ttou edvyalubaetcea tuhes epeLrEfoSrmflaonwce aonf dthep ower
p3ro. pCoasseed D aensacrlyiptitcioanl wind farm model. The wind farm has a total rated power capacity of 160 MW
predictions[26,36]andpowermeasurements[17,37]areavailabletoevaluatetheperformanceofthe
and coWnsei sstesl eocft eeidg hthtye VHeosrtnass VRe-8v0 o wffisnhdo rteu rwbiinndes fwarimth ians aan c aarseea sotuf adpyp breocxaiumsaet eLlEyS 2 0fl okwm 2a. nItd i sp loowcaetre d
proposedanalyticalwindfarmmodel. Thewindfarmhasatotalratedpowercapacityof160MWand
inp rthede icNtioorntsh [S26e,a3,6 a] papnrdo pxoimwaetre mlye 1a5su krmem oefnft st h[1e7 w,3e7s] taerren amvoasilta bploei ntot eovf aDlueantem tahrek p. eErafochrm tuanrbcein oef hthaes a
consistsofeightyVestasV-80windturbineswithinanareaofapproximately20km2. Itislocatedin
roptroorp dosiaemd eatnearl yotfi c𝑑al =w8in0d 𝑚 fa ramnd m ao dheulb. Thheei gwhitn odf fa𝐻rℎm𝑢𝑏 h=as7 a0 t𝑚ot a(la rbaotvede pseoaw leerv ceal)p. aFciigtyu roef 136 s0h MowWs a
theNorthSea,approximately15kmoffthewesternmostpointofDenmark. Eachturbinehasarotor
scahnedm caotnicsi sotfs othf ee iHghotryn Vs eRsteavs Vw-i8n0d w fianrdm t ulrabyionuest. wTihthei nw ainn dar efaar omf ahpapsr oax rimhoamtelbyo 2id0 ksmha2.p Iet iws liothca wtedin d
diamettueinrrb otihnfeed sN = oarrtr8ha0 nSmgeead,a anipdnp ra8o xhciumoblauthmeleyni sg1 h5( taklomigf noHefdfh uthbwe =i twh7e s0tthemer nEm(aaobsstot- Wvpeoeissntet adofil reDevceetnilom)n.a)F rkiag.n uEdra ec1h30 tsurhrobowiwnse s (htauasrs ncaeh de matic
of theaHpropotrorornx dsimiaRameteevltyew r 7oi°nf cd𝑑ou=fan8rte0mr 𝑚cllo aacynkodwu iast e.h ufTrboh mhee iwgthhietn oNdf o𝐻frathrm-S=ohu7ta0hs 𝑚da i(rraehbcotoivomen b)s.eo aTi dhleevs ehtula)r.p bFieingewusr ieat hr3e swrheoignwudsl aatr ulyr bines
ℎ𝑢𝑏
arrangsepsdcahcieenmd,8a wtciciot hlou fa m tmhnei snHi(moarluinmgsn Rsepedvac wwiniigtnh db etfthawremeEe nala stytwo-Wuo tc.e oTsnthsdee ciwrueitnicvdtei o ftanur)rmbai nnheadss 1oa0f r7rh oroowmtosbro (ditduia rsmnheaetpdeer asw.p i pthr owxiinmd ately7◦
turbines arranged in 8 columns (aligned with the East-West direction) and 10 rows (turned
counterclockwisefromtheNorth-Southdirection). Theturbinesareregularlyspaced,withaminimum
approximately 7° counterclockwise from the North-South direction). The turbines are regularly
spacingbetweentwoconsecutiveturbinesof7rotordiameters.
spaced, with a minimum spacing between two consecutive turbines of 7 rotor diameters.
Figure 3. Layout of the Horns Rev wind farm. Distances are normalized by the rotor diameter 𝑑=80.
Figure 3. Layout of the Horns Rev wind farm. Distances are normalized by the rotor diameter 𝑑=80.
Fi gure3.LayoutoftheHornsRevwindfarm.Distancesarenormalizedbytherotordiameterd=80.

Energies2016,9,741 7of13
Thewindturbinepowercurveandthrustcoefficientcurve,bothofwhichareinputsrequired
bythenewanalyticalwindfarmmodel,aretypicallyavailablefromthemanufacturer. Thecurves
for the Vestas V-80 turbine are shown in Figure 4. The same curves were also used by Wu and
Porté-Agel[36]intheirLESstudyofwakeflowsintheHornsRevwindfarm. Tospecifytheincoming
flow conditions, the aerodynamic surface roughness of the sea surface was set to z = 0.0002 m.
0
Theinflowwindconditionischaracterizedbyaturbulenceintensityof7.7%atthehubheightand
an average velocity of 8 ms−1 at the same height. These conditions are the same as those for the
aEvnearigliaesb 2le01p6,o 9w, 7e4r1 measurements[17],LESflow,andpowerresults[36]. 7 of 13
Figure 4. Measured and simulated power curve and thrust coefficient curve of the Vestas V-80 2 MW
Figure4.MeasuredandsimulatedpowercurveandthrustcoefficientcurveoftheVestasV-802MW
wind turbine, for a range of wind speeds (Source: Wu and Porté-Agel, 2014).
windturbine,forarangeofwindspeeds(Source:WuandPorté-Agel,2014).
The wind turbine power curve and thrust coefficient curve, both of which are inputs required
4. ResultsandDiscussion
by the new analytical wind farm model, are typically available from the manufacturer. The curves
for thIne Vtheisstasse cVti-o8n0 ,tpurrebdinicet aiorne sshoobwtanin iend Fwigiuthret 4h.e Tnheew saamnea lcyutircvaelsm woedree laflosor tuhseedtu bryb iWneuw anakde Psoarntéd-
aAsgsoelc i[a3t6e]d inp tohweierr LlEosSs setsuidnyt ohfe wHaokren fsloRwevs iwn itnhde Hfaormrnsa Rreevp rwesinendt feadr.mT. hTeo rsepseuclitfsya trheea ilnscoocmoimngp aflroewd
wcointhdiatvioanilsa, btlheep aoewroedrymneaamsuicr esmurefnatcse [r1o7u,3g7h]naensds LoEf Sthdea tsaea[ 2s6u,3r6fa],cea swwaesl lseats two it𝑧hp=re0d.0ic0t0io2n 𝑚s.f rTohme
0
ainnfleoxwis twinignda ncaolnydtiictaiolnto ips -chhaatrwacatkereizmedo dbeyl. aT thuerbtouple-nhcaet winateknesmityo doef l7i.s7%ba aset dthoen htuhbe ohneieghptr oapnods eadn
bayveKraagtiec evtealol.c[i6ty] aonfd 8i s𝑚co𝑠−m1m aot ntlhyeu ssaemdein haeivgahrti.e tTyhoefses ocfotwndariteio(ne.sg .a,rteh ethWe insadmAet laass Athnoasley sfiosr atnhde
Aavpapilliacbalteio pnoPwroerg rmameas(WurAemsPe)natns d[1t7h]e, LPAESR fKlomwo, daenld). pInowtheisr rtoepsu-hltast [w36a]k. emodel,thewakegrowthrate
issettoaconstant(andspatiallyuniform)valueof0.04,whichisbasedontheformulaproposedby
F4r. aRnedssuelntse atnadl. [D1i4s]c.ussion
ThesimulatedtotalnormalizedpoweroutputfromtheHornsRevwindfarmcalculatedwith
In this section, predictions obtained with the new analytical model for the turbine wakes and
thenewmodel,LES[26],andthetop-hatmodel[6]isshowninFigure5forawiderangeofwind
associated power losses in the Horns Rev wind farm are presented. The results are also compared
directions (from 173◦ to 353◦). This enables an extensive model evaluation over a variety of both
with available power measurements [17,37] and LES data [26,36], as well as with predictions from an
full-wakeandpartial-wakeoperatingconditions. Furthermore,wenormalizethesimulatedpower
existing analytical top-hat wake model. The top-hat wake model is based on the one proposed by
outputbythepowerofanequivalentnumberofstand-alonewindturbinesoperatinginthesame
Katic et al. [6] and is commonly used in a variety of software (e.g., the Wind Atlas Analysis and
incomingwindcondition. AsshowninFigure1,agoodagreementisfoundbetweentheproposed
Application Program (WAsP) and the PARK model). In this top-hat wake model, the wake growth
analyticalmodelandLES,whilethetop-hatmodelsignificantlyunderpredictsthenormalizedpower.
rate is set to a constant (and spatially uniform) value of 0.04, which is based on the formula proposed
Furthermore,windfarmpowerproductionsubstantiallydecreases(approximately30%)asthewind
by Frandsen et al. [14].
farmisexposedtowinddirectionangles(173◦,270◦,and353◦),correspondingtofull-wakeconditions
The simulated total normalized power output from the Horns Rev wind farm calculated with
withshortstreamwisedistancesbetweenconsecutivewindturbines. Additionally,whenthewind
the new model, LES [26], and the top-hat model [6] is shown in Figure 5 for a wide range of wind
farmisexposedtothewinddirectionsinwhichthereisalargestreamwisedistancebetweenturbines
directions (from 173° to 353°). This enables an extensive model evaluation over a variety of both
(e.g.,185◦ and340◦),severallocalmaximacanbedistinguished.
full-wake and partial-wake operating conditions. Furthermore, we normalize the simulated power
output by the power of an equivalent number of stand-alone wind turbines operating in the same
incoming wind condition. As shown in Figure 1, a good agreement is found between the proposed
analytical model and LES, while the top-hat model significantly under predicts the normalized
power. Furthermore, wind farm power production substantially decreases (approximately 30%) as
the wind farm is exposed to wind direction angles (173°, 270°, and 353°), corresponding to full-
wake conditions with short streamwise distances between consecutive wind turbines. Additionally,
when the wind farm is exposed to the wind directions in which there is a large streamwise distance
between turbines (e.g., 185° and 340°), several local maxima can be distinguished.

Energies 2016, 9, 741 8 of 13
Energies2016,9,741 8of13
Energies 2016, 9, 741 8 of 13
Figure 5. Distribution of the normalized Horns Rev wind farm power output obtained with the new
analytical model and LES for different wind directions.
Next, the performance of different multiple wake superposition approaches is evaluated. For
this purpose, we compare the normalized power output simulated with the new analytical model
using both velocity deficit superposition (i.e., Equation (12)) and energy deficit superposition (i.e.,
Equation (8)) with the one obtained with LES. The normalized power output as a function of turbine
row (averaged over columns 2, 3, and 4) in the wind farm is shown in Figure 2. The difference
between the inflow velocity at the turbine and the wake velocity is used for calculation of the velocity
and energy deficits. It is important to mention that if the difference between the incoming velocity to
the tFu Fii rgg buu inrree e 5 5 a.. nDD diiss tt trr hiibb euu wttiioo ann k eoo ff vtthe hel e o nn coo itrr ymm iaa sll iizu zee sdd e dHH , oo urrnn nss r eRR aee lvv is ww ticiinn ndd eff gaara rmm ti vpp eoo ww veeerl r o oo cuu ittt ipp euu st t coo abb nttaa io inn cee cdd u wr w ia itths h ta thh er e e nn see uww lt of a
largeaa nnnaaullyymttiiccbaaellr mm ooofdd eetllu aarnnbddi nLLeEE SSr ffooowrr dds.ii ffffAeerrsee nnstt hwwoiiwnnddn dd iiirrnee ccttFiiooignnuss..r e 6, although energy deficit superposition
substantially overestimates the normalized power output, velocity deficit superposition shows good
agreeNmeexnt,t twheit hp eLrEfoSr. m ance of different multiple wake superposition approaches is evaluated. For
Next, the performance of different multiple wake superposition approaches is evaluated.
this pTuor pshooswe, twhee icmompapcat roef tthhee lnoocraml walaizkeed g rpoowwtehr roautet pount w siimndu flaartemd pwoiwthe rt hper endeiwcti oann,a tlhyeti csaiml muloadteedl
For this purpose, we compare the normalized power output simulated with the new analytical
unsoirnmg ablioztehd v peloowcietyr doeuftipcuitt suopbtearipnoesdit iuosni n(ig.e .c, oEnqsutaantito nan (d1 2v))a arinadb leen weragkye d gefriocwit tshu praetrepso s(itthioen l a(it.tee.r,
modelusingbothvelocitydeficitsuperposition(i.e.,Equation(12))andenergydeficitsuperposition
Ecaqlucuatliaotned ( 8b)a) swedit ho nth teh oe nloe coabl tsatirneeadm wwiitshe LtuErSb. uTlhene cneo irnmteanliszietyd, pEoqwuaetri oonu t(p1u5)t) a iss ac ofumnpcatiroend owf ittuhr LbiEnSe.
(i.e.,Equation(8))withtheoneobtainedwithLES.Thenormalizedpoweroutputasafunctionof
rAosw s h(aovwenra igne Fdi gouvreer 7c, orleuamsonnsa b2l, e3 a, garnedem 4e) nitn b tehtwe eweinn dth efa arnma liyst ischaol wmno dienl aFnigdu LreE S2 .c aTnh eb ed aifcfherieevnecde
turbinerow(averagedovercolumns2,3,and4)inthewindfarmisshowninFigure2. Thedifference
buestiwnge ean v tahreia ibnlfelo wwa kvee lgorcoitwy taht rthatee t. uInrb cionne tarnasdt ,t hases wumakine gv eal ococintsyt aisn ut swedak feo rg croalwcuthla rtaioten loefa dthse t ov eal occleitayr
betweentheinflowvelocityattheturbineandthewakevelocityisusedforcalculationofthevelocity
aunndd eerneesrtgimy adteiofinci tosf. tIht eis nimorpmoarltiaznetd t op omweenrt ioount tphuatt. iTf hthise ids ifbfeecraeunscee, bientswideee nth teh ew iinncdo mfairnmg, vtheleo wcitayk teos
andenergydeficits. Itisimportanttomentionthatifthedifferencebetweentheincomingvelocityto
trheec otvuerrb ifnaset earn (da nthde t hwuask hea vveel ao cliatryg eisr ugrsoewd,t hu nraretea)l idstuice tnoe gthaeti ivnec rveealsoecdit ifelos wca enn torcaciunrm aesn ta inredsuuclte do fb ay
theturbineandthewakevelocityisused,unrealisticnegativevelocitiescanoccurasaresultofalarge
ltahreg ere lnautimveblyer h iogfh etur rtbuirnbeu lreonwces .l eAvesl ss hino wthne wina kFeisg, ucroem 6p,a raeldth wouitghh t heen einrgcoym dinegfi cfilto wsu. pOeurpr oresistuioltns
numberofturbinerows. AsshowninFigure6,althoughenergydeficitsuperpositionsubstantially
ssuhboswta nthtiea lilmy povoertraenstciem oaft etsa tkhien gn oirnmtoa laizcecdou pnotw tehre oiuntcprueat,s vedel olecivteyl doeff itcuitr sbuupleenrpceo siintitoenn ssihtyo wans dg otohde
overestimatesthenormalizedpoweroutput,velocitydeficitsuperpositionshowsgoodagreement
aagssroeecimateendt iwncitrhe aLsEeSd. g rowth rate for the prediction of wakes and power inside wind farms.
withLES.
To show the impact of the local wake growth rate on wind farm power prediction, the simulated
normalized power output obtained using constant and variable wake growth rates (the latter
calculated based on the local streamwise turbulence intensity, Equation (15)) is compared with LES.
As shown in Figure 7, reasonable agreement between the analytical model and LES can be achieved
using a variable wake growth rate. In contrast, assuming a constant wake growth rate leads to a clear
underestimation of the normalized power output. This is because, inside the wind farm, the wakes
recover faster (and thus have a larger growth rate) due to the increased flow entrainment induced by
the relatively higher turbulence levels in the wakes, compared with the incoming flow. Our results
show the importance of taking into account the increased level of turbulence intensity and the
associated increased growth rate for the prediction of wakes and power inside wind farms.
F
F
i
i
g
g
u
u
r
r
e
e
6
6
.
.
C
C
o
o
m
m
p
p
a
a
r
r
i
i
s
s
o
o
n
n
o
o
f
f
t
t
h
h
e
e
w
w
i
i
n
n
d
d
-
-
f
f
a
a
r
r
m
m
p
p
o
o
w
w
e
e
r
r
o
o
u
u
tp
tp
u
u
t
t
f o
fo
r
r
θ
𝜃 𝑤𝑖𝑛𝑑==
27
2
0
7◦0
o
°
b
o
ta
b
i
t
n
a
e
in
d
e
u
d
s
u
in
s
g
in
L
g
E
L
S
E
a
S
s
a
w
s
e
w
ll
e
a
l
s
l
wind
tahse thnee wneawn aalnyatilcyatilcmalo mdeoldweli twhibtho tbhoethn eerngeyrgayn danvde lvoeclitoycidtye fidceifticsuitp seurppeorspitoiosintiso.ns.
Figure 8 shows the normalized power output for three wind sectors (i.e., ±5°, ±10°, and ±15°)
Toshowtheimpactofthelocalwakegrowthrateonwindfarmpowerprediction,thesimulated
centered on three mean wind directions (𝜃 = 270°, 222°, and 312°) simulated by the new analytical
normalizedpoweroutputobtainedusingco𝑤n𝑖𝑛s𝑑tantandvariablewakegrowthrates(thelattercalculated
model and WAsP, as well as the measurements [37]. As shown in this figure, WAsP clearly tends to
basedonthelocalstreamwiseturbulenceintensity,Equation(15))iscomparedwithLES.Asshownin
under predict the power output, while a very good agreement between the measurements and the
Figure7,reasonableagreementbetweentheanalyticalmodelandLEScanbeachievedusingavariable
w akegrowthrate. Incontrast,assumingaconstantwakegrowthrateleadstoaclearunderestimation
ofthenormalizedpoweroutput. Thisisbecause,insidethewindfarm,thewakesrecoverfaster(and
thushavealargergrowthrate)duetotheincreasedflowentrainmentinducedbytherelativelyhigher
Figure 6. Comparison of the wind-farm power output for 𝜃 =270° obtained using LES as well
turbulencelevelsinthewakes,comparedwiththeincoming𝑤fl𝑖𝑛o𝑑w. Ourresultsshowtheimportanceof
as the new analytical model with both energy and velocity deficit superpositions.
takingintoaccounttheincreasedlevelofturbulenceintensityandtheassociatedincreasedgrowth
rateforthepredictionofwakesandpowerinsidewindfarms.
Figure 8 shows the normalized power output for three wind sectors (i.e., ±5°, ±10°, and ±15°)
Figure8showsthenormalizedpoweroutputforthreewindsectors(i.e.,±5◦,±10◦,and±15◦)
centered on three mean wind directions (𝜃 = 270°, 222°, and 312°) simulated by the new analytical
centeredonthreemeanwinddirections(θ 𝑤𝑖𝑛𝑑 =270◦,222◦,and312◦)simulatedbythenewanalytical
model and WAsP, as well as the measuremwinednts [37]. As shown in this figure, WAsP clearly tends to
under predict the power output, while a very good agreement between the measurements and the

Energies2016,9,741 9of13
modelandWAsP,aswellasthemeasurements[37]. Asshowninthisfigure,WAsPclearlytendsto
Energies 2016, 9, 741 9 of 13
Enuerngidese 2r01p6r, e9d, 7i4c1t thepoweroutput,whileaverygoodagreementbetweenthemeasurementsa9n odf 1t3h e
proposedmodelisfound. Thisresultrevealsthefactthatconsideringatop-hatshapefornormalized
proposed model is found. This result reveals the fact that considering a top-hat shape for normalized
prvoeploosceitdy mdeofidceilt icsa fnoulenadd. tTohsius bresstaunltt iraelveerarlosr tihne bfaoctht tfhualtl- cwoankseidaenridnpg aar ttioapl--whaatk sehcaopned fiotiro nnosr.malized
velocity deficit can lead to substantial error in both full-wake and partial-wake conditions.
velocity deficit can lead to substantial error in both full-wake and partial-wake conditions.
F
F
i
i
g
g
u
u
r
r
e
e
7
7
.
.
C
C
o
o
m
mp
p
a
a
r
r
i
i
s
s
o
o
n
n
o
o
f
f
t
t
h
h
e
e
p
p
o
o
w
w
e
e
r
r
o
o
u
u
t
t
p
p
u
u
t
t
f
f
o
o
r
r θ
𝜃
𝑤𝑖𝑛𝑑 =
=
2
2
7
7
0
0◦°
o
o
b
b
t
t
a
a
i
i
n
n
e
e
d
d
w
w
i
i
t
t
h
h
t
t
h
h
e
e
n
n
e
e
w
w
a
a
n
n
a
a
l
l
y
y
t
t
i
i
c
c
a
a
l
l
m
m
o
o
d
d
e
e
l
l
Figure 7. Comparison of the power output for 𝜃 win d= 270° obtained with the new analytical model
using a constant wake growth rate and a vari𝑤a𝑖b𝑛l𝑑e wake growth rate based on the local streamwise
usingaconstantwakegrowthrateandavariablewakegrowthratebasedonthelocalstreamwise
using a constant wake growth rate and a variable wake growth rate based on the local streamwise
turbulence intensity.
turbulenceintensity.
turbulence intensity.
(a) (b)
(a) (b)
(c)
(c)
Figure 8. Comparison of the simulated and observed power output centered on three mean wind
Figure 8. Comparison of the simulated and observed power output centered on three mean wind
Fdiigreucrteio8n.s C𝜃omp a=r i2s7o0n° (oaf);t h22e2s°i m(bu) alantded 31a2n°d (co).b Ssyermvbeodlsp, oliwneesr, oaundtp duatscheendt elirneeds odnenthotree ethme eoabnsewrviendd,
𝑤𝑖𝑛𝑑
dir
dn
e
ie
c
rw
t
e
i
c
o
ta
n
ino
s
na
𝜃
lsy𝑤θt𝑖iw 𝑛ci 𝑑an ld
=
m =
27
o2
0
d7
°
0e
(◦
l
a
, (
)
aa
;
n
2
);d
2
2
2
2W
°
2
(◦
A
b
(
)
sb P
a
)
n
da
d
na
3
tda
1
,3
2
1
°
r e2
(
s
c◦
p
)
(
.
e c
S
c)
y
.ti
m
Svye
b
ml
o
y
l
b.
s
oB
,
l
l
ls
i
u
n
,el
e
i,
s
nr
,
e e
a
sd
n
,,
d
a an
d
nd
a
d
s
d
h
ba
e
lsa
d
hc e
l
k
i
d
n
c
e
loi
s
nl o
d
ers
e
s
n
d r
o
ee
t
np
e
o r
t
te
h
es
e
et h
o
ne
b
t
s
o±
e
b5
r
°s
v
,e
e
r±
d
v1
,
e0 d°,,
ne n w ane wd an ±a a 1n l 5 y a° t l i yw c t a ii l cn a m dl o sme d oc e td l o , e r a ls, n , a d rne s W dpW A ec s At P ivs Pe d l a dy t .a a t , a r , e r s e p s e p c e t c iv ti e v l e y l . y B . l B u l e u , e r , e r d ed , a , n an d d b b la l c a k ck co co lo lo rs r s re re p p re re s s e e n n t t ±±5° 5 , ◦± , 1±0° 1 , 0 ◦,
an
a
d
n
±
d
15±°
1
w 5◦in
w
d
i n
se
d
ct
s
o
e
r
c
s
t
,
o
r
r
e
s
s
,
p
re
e
s
c
p
ti
e
v
c
e
t
l
i
y
v
.
e ly.
One of the main features of the new analytical wind farm model is the capability of computing
One of the main features of the new analytical wind farm model is the capability of computing
the mOenaeno vfethloecmitya ifniefleda tiunrseisdoe fat hweinnedw faarnmal yatnicda ltwhei nadssfoacrmiatmedo dpeolwisetrh oeuctappuatb iilnit ya ocfocmopmuptuattiionngatlhlye
the mean velocity field inside a wind farm and the associated power output in a computationally
meffeiacnievnet lwocaiyty wfihelidle ikneseidpeinagw thined acfacrumraacyn dactcheepatsasbolcei.a Fteigdupreo w9 esrhoowutsp au ttwinoa-dciommepnusitoatniaoln caollnytoefufirc pielnott
efficient way while keeping the accuracy acceptable. Figure 9 shows a two-dimensional contour plot
wofa ythwe hstirleeakmeewpiisneg vtehleocaictcyu oranc ya ahcocreipzotanbtlael. pFliagnuer eat9 hshuobw lesvaelt wsiom-duilmateends iboyn aLlEcSo n[2to6u,3r6p],l othteo fntehwe
of the streamwise velocity on a horizontal plane at hub level simulated by LES [26,36], the new
analytical model, and the classical top-hat analytical model [6]. It should be mentioned that the
analytical model, and the classical top-hat analytical model [6]. It should be mentioned that the
analytical wake models can only predict the velocity deficit in the far-wake region (after a downwind
analytical wake models can only predict the velocity deficit in the far-wake region (after a downwind
distance of approximately two rotor diameters from each turbine) where the wake flows have a self-
distance of approximately two rotor diameters from each turbine) where the wake flows have a self-
similar Gaussian behavior and can be described by global parameters such as the thrust coefficient.
similar Gaussian behavior and can be described by global parameters such as the thrust coefficient.
To this effect, a white rectangle is placed in the near wake region in Figure 9. Reasonable agreement
To this effect, a white rectangle is placed in the near wake region in Figure 9. Reasonable agreement

Energies2016,9,741 10of13
streamwisevelocityonahorizontalplaneathublevelsimulatedbyLES[26,36],thenewanalytical
model, and the classical top-hat analytical model [6]. It should be mentioned that the analytical
wakemodelscanonlypredictthevelocitydeficitinthefar-wakeregion(afteradownwinddistance
ofapproximatelytworotordiametersfromeachturbine)wherethewakeflowshaveaself-similar
Gaussianbehaviorandcanbedescribedbyglobalparameterssuchasthethrustcoefficient. Tothis
Energies 2016, 9, 741 10 of 13
effect,awhiterectangleisplacedinthenearwakeregioninFigure9. Reasonableagreementbetween
tbheetwpreoepno stehde apnraolpytoisceadlm aondaelyltaincadl LmESodiseflo aunndd ,LwEhSi leist hfeoutonpd-,h awthmiloed ethleg ivtoeps-ahlaets smreoadlieslt igcipvreesd aic tlieosns
orefatlhisetivc eplorecditiyctflioonw offi ethlde vdeuleoctiotyt hfleowto pfi-ehladt dausseu tmo pthtieo ntopfo-hratth easvsuelmocpittiyond efofirc itth,ew vheilcohcirteys udletfsiciint,
awuhnicifho rrmesuwltask ienv ae luonciitfyordmis twriabkuet iovneloincitthye dsipsatrnibwuitsieodn irinec tthioen s.pFaunrwthiesrem doirreec,tiitoins.o Fbuvritohuesrmthoartew, iatk ies
floobwvisouasre trheastp wonaskieb leflofowrsa asrieg nriefiscpaonntsribedleu fcotiro na osfigtnhiefivcaenlot criteyduimctmioend oiaft etlhye uvpesltorceiatym iomfmtheedwiatineldy
tuuprbstirneeasmin osfi dtheet hweiwndin tdurfbairnme.s inside the wind farm.
(a) (b)
(c)
Figure 9. Comparison of the time-averaged streamwise velocity at a horizontal plane at hub height:
Figure9.Comparisonofthetime-averagedstreamwisevelocityatahorizontalplaneathubheight:
(a) LES; (b) new analytical model and (c) top-hat model.
(a)LES;(b)newanalyticalmodeland(c)top-hatmodel.
As discussed previously, the wake growth rate is dependent on the local streamwise turbulence
Asdiscussedpreviously,thewakegrowthrateisdependentonthelocalstreamwiseturbulence
intensity. Therefore, the local streamwise turbulence intensity in the wind farm should be predicted
intensity. Therefore,thelocalstreamwiseturbulenceintensityinthewindfarmshouldbepredicted
in the analytical wind farm model. Furthermore, it is imperative to estimate the level of turbulence
intheanalyticalwindfarmmodel. Furthermore,itisimperativetoestimatethelevelofturbulence
intensity at the turbine locations to investigate the impact of fatigue loading due to turbulence on the
intensityattheturbinelocationstoinvestigatetheimpactoffatigueloadingduetoturbulenceonthe
turbines. Figure 10 presents the level of streamwise turbulence intensity at hub height in the wind
turbines. Figure10presentsthelevelofstreamwiseturbulenceintensityathubheightinthewind
farm obtained from the models of Quarton and Ainslie [30], Hassan and Hassan [31], and Crespo and
farmobtainedfromthemodelsofQuartonandAinslie[30],HassanandHassan[31],andCrespoand
Hernandez [32], as well as the LES predictions. It clearly shows that both the models of Quarton and
Hernandez[32],aswellastheLESpredictions. ItclearlyshowsthatboththemodelsofQuartonand
Ainslie and of Hassan and Hassan over predict the level of streamwise turbulence intensity when
AinslieandofHassanandHassanoverpredictthelevelofstreamwiseturbulenceintensitywhen
compared with LES. In contrast, the model of Crespo and Hernandez, which is used in the new
compared with LES. In contrast, the model of Crespo and Hernandez, which is used in the new
proposed model, predicts turbulence intensity levels that are very similar to those simulated by LES.
proposedmodel,predictsturbulenceintensitylevelsthatareverysimilartothosesimulatedbyLES.

Energies2016,9,741 11of13
Energies 2016, 9, 741 11 of 13
Figure 10. Comparison of the streamwise turbulence intensity at hub height immediately upstream
Figure10.Comparisonofthestreamwiseturbulenceintensityathubheightimmediatelyupstreamof
of each turbine row, obtained with LES and three simple models.
eachturbinerow,obtainedwithLESandthreesimplemodels.
5. Conclusions
5. Conclusions
A new analytical wind-farm wake model is proposed to predict wake flows and associated
Anewanalyticalwind-farmwakemodelisproposedtopredictwakeflowsandassociatedpower
power losses inside wind farms. The model combines the self-similar Gaussian model recently
lossesinsidewindfarms. Themodelcombinestheself-similarGaussianmodelrecentlydevelopedby
developed by Bastankhah and Porté-Agel [15] for stand-alone wind turbine wakes with a new wake
BastankhahandPorté-Agel[15]forstand-alonewindturbinewakeswithanewwakesuperposition
superposition procedure that is based on the superposition of velocity deficits. This combination
procedure that is based on the superposition of velocity deficits. This combination guarantees
guarantees that mass and momentum are conserved by the model. The growth rate of each individual
that mass and momentum are conserved by the model. The growth rate of each individual wake
wake needs to be specified and is computed using an empirical expression based on the local
needstobespecifiedandiscomputedusinganempiricalexpressionbasedonthelocalstreamwise
streamwise turbulence intensity, which is predicted inside the wind farm using the model proposed
turbulenceintensity,whichispredictedinsidethewindfarmusingthemodelproposedbyCrespoand
by Crespo and Hernandes [32]. Finally, the power curve of the wind turbines is used to estimate the
Hernandes[32].Finally,thepowercurveofthewindturbinesisusedtoestimatethepowerproduction.
power production.
TheHornsRevwindfarmwasselectedasavalidationcasestudybecausepowermeasurements
The Horns Rev wind farm was selected as a validation case study because power measurements
andpreviousLESpredictionsofthewakeflowsandturbinepowerareavailableforawiderange
and previous LES predictions of the wake flows and turbine power are available for a wide range of
ofinflowconditions. ComparisonbetweenthemeasurementsandLESresultsrevealthatthenew
inflow conditions. Comparison between the measurements and LES results reveal that the new
analytical wind-farm model yields reasonably accurate predictions of the power output from the
analytical wind-farm model yields reasonably accurate predictions of the power output from the
HornsRevwindfarmforallofthewinddirectionsconsideredinthisstudy. Additionally,weshow
Horns Rev wind farm for all of the wind directions considered in this study. Additionally, we show
thatthepowerpredictionofthenewanalyticalwindfarmmodelissignificantlybetterthantheone
that the power prediction of the new analytical wind farm model is significantly better than the one
estimatedbyWAsP.
estimated by WAsP.
Future research will consider the development of more general parametrization of the local
Future research will consider the development of more general parametrization of the local
turbulenceintensityandthewakegrowthrate,whichcanthenbeusedbythenewmodelforawider
turbulence intensity and the wake growth rate, which can then be used by the new model for a wider
range of inflow characteristics (e.g., including thermal stability) and turbine operation conditions
range of inflow characteristics (e.g., including thermal stability) and turbine operation conditions
(e.g., turbine down-regulation or yawing). Furthermore, because of its low computational cost,
(e.g., turbine down-regulation or yawing). Furthermore, because of its low computational cost, the
thenewlyproposedmodelcanbeusedfortheoptimizationofwindfarmlayoutstomaximizepower
newly proposed model can be used for the optimization of wind farm layouts to maximize power
outputandminimizethefatigueloadonthewindturbines.
output and minimize the fatigue load on the wind turbines.
AAcckknnoowwlleeddggmmeennttss:: TThihsisre sreeasrecahrwcha swsuapsp osrutepdpobrytethde Sbwy issthNe atSiowniaslsS cNieantcieonFaolu nSdcaiteinocne( grFaonutn2d0a0t0i2o1n- 13(2g1r2a2n)t,
theSwissInnovationandTechnologyCommittee(CTI)andtheSwissFederalOfficeofEnergy(OFEN)withinthe
200021-132122), the Swiss Innovation and Technology Committee (CTI) and the Swiss Federal Office of Energy
contextoftheSwissCompetenceCenterforEnergyResearch‘FURIES:FutureSwissElectricalInfrastructure’.
(OFEN) within the context of the Swiss Competence Center for Energy Research ‘FURIES: Future Swiss Electrical
TheauthorsalsothankYu-TingWuforprovidingtheWAsPdata.
Infrastructure’. The authors also thank Yu-Ting Wu for providing the WAsP data.
AuthorContributions:ThisstudywasdoneasAminNiayifar’sinternshipatWindEngineeringandRenewable
EAnuetrhgoyr LCaobnotrraibtourtyio(WnsI: RTEh)iss ustpuedryv iwseads bdyonFee ransa AndmoinP Noritaéy-Aifagre’ls. internship at Wind Engineering and Renewable
Energy Laboratory (WIRE) supervised by Fernando Porté-Agel.
ConflictsofInterest:Theauthorsdeclarenoconflictofinterest.
Conflicts of Interest: The authors declare no conflict of interest.
References
References
1. Globalwind Energy Council. Globalwind Report: Annual Market Update 2012. Available online:
1. GHltotpb:a/l/wwinwdw .GEnweercg.yN etC/owupn-cciol.n teGnlto/buaplwloiandds /2R0e1p2/or0t6: /aAnnnnuualarle poMrta2r0k1e2tl owUrpeds.aptde f(2a0cc1e2s. seAdvoanil3a0blJeu neon20li1n3e):.
Http://www.Gwec.Net/wp-content/uploads/2012/06/annual report 2012 lowres.pdf (accessed on 30 June 2013).
2. Barthelmie, R.J.; Pryor, S.; Frandsen, S.T.; Hansen, K.S.; Schepers, J.; Rados, K.; Schlez, W.; Neubert, A.;
Jensen, L.; Neckelmann, S. Quantifying the impact of wind turbine wakes on power output at offshore
wind farms. J. Atmos. Oceanic Technol. 2010, 27, 1302–1317.

Energies2016,9,741 12of13
2. Barthelmie,R.J.; Pryor,S.; Frandsen,S.T.; Hansen,K.S.; Schepers,J.; Rados,K.; Schlez,W.; Neubert,A.;
Jensen,L.;Neckelmann,S.Quantifyingtheimpactofwindturbinewakesonpoweroutputatoffshorewind
farms.J.Atmos.OceanicTechnol.2010,27,1302–1317.[CrossRef]
3. Crespo,A.;Hernandez,J.;Frandsen,S.Surveyofmodellingmethodsforwindturbinewakesandwind
farms.WindEnergy1999,2,1–24.[CrossRef]
4. Chowdhury,S.;Zhang,J.;Messac,A.;Castillo,L.Optimizingthearrangementandtheselectionofturbines
forwindfarmssubjecttovaryingwindconditions.Renew.Energy2013,52,273–282.[CrossRef]
5. Lissaman, P.B.S. Energy effectiveness of arbitrary arrays of wind turbines. J. Energy 1979, 3, 323–328.
[CrossRef]
6. Katic,I.;Højstrup,J.;Jensen,N.ASimpleModelforClusterEfficiency.InProceedingsoftheEuropeanWind
EnergyAssociationConferenceandExhibition,Rome,Italy,1986;pp.407–410.
7. Frandsen,S.Onthewindspeedreductioninthecenteroflargeclustersofwindturbines. J.WindEng.
Ind.Aerodyn.1992,39,251–265.[CrossRef]
8. Calaf,M.;Meneveau,C.;Meyers,J.Largeeddysimulationstudyoffullydevelopedwind-turbinearray
boundarylayers.Phys.Fluids2010,22,015110.[CrossRef]
9. Abkar,M.;Porté-Agel,F.Theeffectoffree-atmospherestratificationonboundary-layerflowandpower
outputfromverylargewindfarms.Energies2013,6,2338–2361.[CrossRef]
10. Stevens,R.J.;Gayme,D.F.;Meneveau,C.Coupledwakeboundarylayermodelofwind-farms. J.Renew.
Sustain.Energy2015,7,023115.[CrossRef]
11. Stevens,R.J.;Gayme,D.F.;Meneveau,C.Generalizedcoupledwakeboundarylayermodel:Applications
andcomparisonswithfieldandlesdatafortwowindfarms.WindEnergy2016.[CrossRef]
12. Jensen,N.O.ANoteonWindGeneratorInteraction;TechnicalreportRis-M-2411;RisøNationalLaboratory:
Roskilde,Denmark,1983.
13. Voutsinas,S.; Rados,K.; Zervos,A.Ontheanalysisofwakeeffectsinwindparks. WindEng. 1990,14,
204–219.
14. Frandsen,S.; Barthelmie,R.; Pryor,S.; Rathmann,O.; Larsen,S.; Højstrup,J.; Thøgersen,M.Analytical
modellingofwindspeeddeficitinlargeoffshorewindfarms.WindEnergy2006,9,39–53.[CrossRef]
15. Bastankhah,M.;Porté-Agel,F.Anewanalyticalmodelforwind-turbinewakes. Renew. Energy2014,70,
116–123.[CrossRef]
16. González,J.S.;Rodriguez,A.G.G.;Mora,J.C.;Santos,J.R.;Payan,M.B.Optimizationofwindfarmturbines
layoutusinganevolutivealgorithm.Renew.Energy2010,35,1671–1681.[CrossRef]
17. Barthelmie,R.;Larsen,G.;Frandsen,S.;Folkerts,L.;Rados,K.;Pryor,S.;Lange,B.;Schepers,G.Comparison
of wake model simulations with offshore wind turbine wake profiles measured by sodar. J. Atmos.
OceanicTechnol.2006,23,888–901.[CrossRef]
18. Crasto, G.; Gravdahl, A.; Castellani, F.; Piccioni, E. Wake modeling with the actuator disc concept.
EnergyProcedia2012,24,385–392.[CrossRef]
19. Garrad Hassan and Partners Ltd. GH Windfarmer Theory Manual; Garrad Hassan and Partners Ltd.:
Bristol,UK,2009.
20. OpenwindTheoreticalBasisandValidation;AWSTruepower,LCC:Albany,NY,USA,2010.
21. Thogersen,M.L.;Sorensen,T.;Nielsen,P.;Grotzner,A.;Chun,S.IntroductiontoWindTurbineWakeModelling
andWakeGeneratedTurbulence;RisøNationalLaboratory,EMDInternationalA/S:Aalborg,Denmark,2006.
22. Chamorro, L.P.; Porté-Agel, F. A wind-tunnel investigation of wind-turbine wakes: Boundary-layer
turbulenceeffects.Boundary-LayerMeteorol.2009,132,129–149.[CrossRef]
23. Wu,Y.-T.;Porté-Agel,F.Atmosphericturbulenceeffectsonwind-turbinewakes:Anlesstudy.Energies2012,
5,5340–5362.[CrossRef]
24. Xie, S.; Archer, C. Self-similarity and turbulence characteristics of wind turbine wakes via large-eddy
simulation.WindEnergy2015,18,1815–1838.[CrossRef]
25. Abkar,M.;Porté-Agel,F.Influenceofatmosphericstabilityonwind-turbinewakes:Alarge-eddysimulation
study.Phys.Fluids2015,27,035104.[CrossRef]
26. Porté-Agel,F.;Wu,Y.-T.;Chen,C.-H.Anumericalstudyoftheeffectsofwinddirectiononturbinewakes
andpowerlossesinalargewindfarm.Energies2013,6,5297–5313.[CrossRef]
27. Abkar,M.;Porté-Agel,F.Meanandturbulentkineticenergybudgetsinsideandaboveverylargewind
farmsunderconventionally-neutralcondition.Renew.Energy2014,70,142–152.[CrossRef]

Energies2016,9,741 13of13
28. Abkar,M.;Sharifi,A.;Porté-Agel,F.Wakeflowinawindfarmduringadiurnalcycle.J.Turbulence2016,17,
1–22.[CrossRef]
29. Porté-Agel,F.;Wu,Y.-T.;Lu,H.;Conzemius,R.J.Large-eddysimulationofatmosphericboundarylayerflow
throughwindturbinesandwindfarms.J.WindEng.Ind.Aerodyn.2011,99,154–168.[CrossRef]
30. Quarton,D.;Ainslie,J.Turbulenceinwindturbinewakes.WindEng.1990,14,15–23.
31. Hassan,U.;Hassan,G.AWindTunnelInvestigationoftheWakeStructurewithinSmallWindTurbineFarms;
HarwellLaboratory,EnergyTechnologySupportUnit:Brighton,UK,1993.
32. Crespo,A.;Hernandez,J.Turbulencecharacteristicsinwind-turbinewakes.J.WindEng.Ind.Aerodyn.1996,
61,71–85.[CrossRef]
33. Vermeulen, P. An Experimental Analysis of Wind Turbine Wakes. In Proceedings of the International
SymposiumonWindEnergySystems,Copenhagen,Denmark,26–29August1980;pp.431–450.
34. Abkar,M.;Porté-Agel,F.Anewwind-farmparameterizationforlarge-scaleatmosphericmodels.J.Renew.
Sustain.Energy2015,7,013121.[CrossRef]
35. Frandsen,S.;Thogersen,M.L.Integratedfatigueloadingforwindturbinesinwindfarmsbycombining
ambientturbulenceandwakes.WindEng.1999,23,327–340.
36. Wu, Y.-T.; Porté-Agel, F. Modeling turbine wakes and power losses within a wind farm using les:
Anapplicationtothehornsrevoffshorewindfarm.Renew.Energy2015,75,945–955.[CrossRef]
37. Barthelmie,R.J.;Hansen,K.;Frandsen,S.T.;Rathmann,O.;Schepers,J.;Schlez,W.;Phillips,J.;Rados,K.;
Zervos,A.;Politis,E.Modellingandmeasuringflowandwindturbinewakesinlargewindfarmsoffshore.
WindEnergy2009,12,431–444.[CrossRef]
©2016bytheauthors;licenseeMDPI,Basel,Switzerland. Thisarticleisanopenaccess
articledistributedunderthetermsandconditionsoftheCreativeCommonsAttribution
(CC-BY)license(http://creativecommons.org/licenses/by/4.0/).