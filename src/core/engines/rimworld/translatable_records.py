"""
The records dictionary counts the number of occurrences of each translatable field in the RimWorld DefInjected XML files.
Used All Translation Github repos under https://github.com/Ludeon/, 
*Note: `label` and `descriptions` are skipped while they are very common, and should be always searched for translation.
records are counted at 2026-07-31
"""

from typing import Any
from pathlib import Path
from collections import Counter

DEFAULT = {
    'label':-1, 
    "description":-1
}

records = {
    "WorkTypeDef": {
        "gerundLabel": 550,
        "verb": 550,
        "labelShort": 527,
        "pawnLabel": 527
    },
    "XenotypeDef": {
        "descriptionShort": 187
    },
    "ResearchTabDef": {
        "generalDescription": 36,
        "generalTitle": 36
    },
    "GeneTemplateDef": {
        "labelShortAdj": 51
    },
    "RaidStrategyDef": {
        "arrivalTextEnemy": 244,
        "letterLabelEnemy": 244,
        "arrivalTextFriendly": 185,
        "letterLabelFriendly": 185
    },
    "BiomeDef": {
        "settleWarning": 99
    },
    "FactionDef": {
        "pawnSingular": 646,
        "pawnsPlural": 626,
        "leaderTitle": 612,
        "messageDefendersAttacking": 499,
        "fixedName": 119,
        "leaderTitleFemale": 74,
        "royalFavorLabel": 20,
        "type": 17,
        "ideoDescription": 17,
        "ideoName": 17,
        "renounceTitleMessage": 3,
        "name": 1
    },
    "PitGateIncidentDef": {
        "letterLabel": 18,
        "letterText": 18,
        "disableEnteringReason": 17
    },
    "StuffCategoryDef": {
        "noun": 133
    },
    "PawnCapacityDef": {
        "labelMechanoids": 96,
        "labelDrones": 46,
        "labelAnomalyEntity": 19
    },
    "TaleDef": {
        "rulesStrings": 2132
    },
    "SkillDef": {
        "skillLabel": 300,
        "rulesStrings": 228
    },
    "GenStepDef": {
        "letterLabel": 18,
        "letterDesc": 17
    },
    "InteractionDef": {
        "rulesStrings": 1329,
        "rulesFiles": 1
    },
    "PawnKindDef": {
        "labelPlural": 5014,
        "labelFemale": 2562,
        "labelMale": 2106,
        "labelFemalePlural": 1712,
        "labelMalePlural": 1642,
        "letterLabel": 136,
        "letterPrompt": 136
    },
    "PlanetLayerDef": {
        "gerundLabel": 34,
        "elevationString": 33,
        "viewGizmoTooltip": 33,
        "travelToLayerDescExtra": 1
    },
    "MemeDef": {
        "adjective": 2508,
        "member": 2508,
        "ideoName": 2318,
        "theme": 1520,
        "rulesStrings": 1147,
        "type": 608,
        "worshipRoomLabel": 171,
        "name": 96
    },
    "HediffDef": {
        "labelNoun": 2771,
        "labelNounPretty": 582,
        "permanentLabel": 455,
        "destroyedLabel": 441,
        "destroyedOutLabel": 276,
        "labelSolidTendedWell": 266,
        "labelTendedWell": 266,
        "labelTendedWellInner": 266,
        "descriptionShort": 262,
        "letterLabel": 186,
        "surgicalDetectionDesc": 142,
        "battleStateLabel": 120,
        "letterText": 118,
        "debugLabel": 117,
        "message": 108,
        "reportString": 108,
        "extraTooltip": 85,
        "descriptionExtra": 68,
        "labelPrefix": 68,
        "letterDesc": 68,
        "instantlyPermanentLabel": 60,
        "overrideLabel": 60,
        "explanation": 51,
        "messageText": 36,
        "notifyMessage": 34,
        "discoverLetterLabel": 25,
        "discoverLetterText": 25,
        "targetPrefix": 19,
        "inspectString": 17,
        "labelInBrackets": 17,
        "messageOnDisappear": 17,
        "overrideLetterDesc": 17,
        "overrideLetterLabel": 17
    },
    "CreepJoinerAggressiveDef": {
        "letterLabel": 2,
        "message": 1
    },
    "QuestScriptDef": {
        "rulesStrings": 5182,
        "slateRef": 4773,
        "questAvailableLetterLabel": 153,
        "raidLetterText": 17,
        "rulesFiles": 9,
        "inspectString": 9,
        "rulesStrings.{idx}": 8,
        "title": 1
    },
    "MentalStateDef": {
        "baseInspectLine": 1014,
        "beginLetter": 801,
        "recoveryMessage": 717,
        "beginLetterLabel": 470
    },
    "RitualBehaviorDef": {
        "desc": 487,
        "spectatorGerund": 283,
        "spectatorsLabel": 283,
        "missingDesc": 247,
        "categoryLabel": 76,
        "jobReportOverride": 51,
        "letterText": 40,
        "letterTitle": 38,
        "customChildDisallowMessage": 36,
        "text": 19,
        "noCandidatesGizmoDesc": 19
    },
    "GatheringDef": {
        "letterText": 47,
        "calledOffMessage": 44,
        "finishedMessage": 44,
        "letterTitle": 43
    },
    "DamageDef": {
        "deathMessage": 1098
    },
    "BodyPartDef": {
        "labelShort": 448,
        "removeRecipeLabelOverride": 23
    },
    "ThingStyleDef": {
        "overrideLabel": 19
    },
    "GameConditionDef": {
        "letterText": 566,
        "endMessage": 419,
        "descriptionFuture": 197,
        "startMessage": 17
    },
    "HistoryAutoRecorderDef": {
        "graphLabelY": 100,
        "valueFormat": 99
    },
    "PawnRelationDef": {
        "labelFemale": 582
    },
    "WeaponTraitDef": {
        "traitAdjectives.{idx}": 2261,
        "chargeNoun": 102,
        "cooldownGerund": 102
    },
    "ScenarioDef": {
        "summary": 196,
        "name": 188,
        "text": 140,
        "customSummary": 34
    },
    "CreepJoinerBaseDef": {
        "letterExtra": 170,
        "letterDesc": 119,
        "letterLabel": 119,
        "message": 17,
        "surgicalInspectionLetterExtra": 17
    },
    "BackstoryDef": {
        "title": 19940,
        "titleShort": 19940,
        "titleFemale": 6272,
        "titleShortFemale": 6230,
        "baseDesc": 5843
    },
    "RaidAgeRestrictionDef": {
        "arrivalTextExtra": 17
    },
    "LifeStageDef": {
        "adjective": 24,
        "customMoodTipString": 22
    },
    "PawnRenderTreeDef": {
        "debugLabel": 377
    },
    "IncidentDef": {
        "letterLabel": 1647,
        "letterText": 1195,
        "letterTextPlural": 34,
        "diseaseLethalLetterText": 19
    },
    "IdeoStoryPatternDef": {
        "rulesStrings": 114
    },
    "ResearchProjectDef": {
        "rulesStrings": 2942,
        "discoveredLetterText": 87,
        "discoveredLetterTitle": 87,
        "customUnlockTexts.{idx}": 17
    },
    "ThinkTreeDef": {
        "crawlingReportStringOverride": 176,
        "reportStringOverride": 19,
        "ReportStringPatrolling": 4
    },
    "SitePartDef": {
        "approachingReportString": 339,
        "approachOrderString": 339,
        "arrivedLetter": 301,
        "mainPartAllThreatsLabel": 193,
        "descriptionDialogue": 5
    },
    "PawnColumnDef": {
        "headerTip": 504
    },
    "CreepjoinerRejectionDef": {
        "letterLabel": 2
    },
    "AbilityDef": {
        "successMessage": 76,
        "failMessage": 38,
        "successMessageNoNegativeThought": 19,
        "confirmationDialogText": 19,
        "mouseTargetingText": 17,
        "failedMessage": 17,
        "cachedTooltip": 4
    },
    "PsychicRitualRoleDef": {
        "psychicRitualLeaveReason_MaxDeathRefusal": 17
    },
    "WeatherDef": {
        "letterLabel": 54,
        "letterText": 54
    },
    "NegativeFishingOutcomeDef": {
        "letterLabel": 198,
        "letterText": 198
    },
    "TraitDef": {
        "labelFemale": 189,
        "mentalBreakInspirationGainReasonText": 23
    },
    "RitualAttachableOutcomeEffectDef": {
        "effectDesc": 133,
        "letterInfoText": 133,
        "requiredMemeList": 8
    },
    "PsychicRitualDef": {
        "outcomeDescription": 272,
        "letterAIArrivedText": 34,
        "letterAICompleteLabel": 34,
        "letterAICompleteText": 34
    },
    "CreepJoinerFormKindDef": {
        "letterLabel": 8
    },
    "PreceptDef": {
        "thoughtStageDescriptions.{idx}": 1224,
        "eventLabel": 196,
        "tipLabelOverride": 38,
        "extraTextPawnDeathLetter": 19
    },
    "HediffGiverSetDef": {
        "letterLabel": 25,
        "letter": 24
    },
    "ThingDef": {
        "labelNoLocation": 3367,
        "namerLabels.{idx}": 901,
        "chargeNoun": 694,
        "cooldownGerund": 629,
        "stuffAdjective": 611,
        "useLabel": 525,
        "inspectString": 490,
        "jobString": 456,
        "activateDescString": 357,
        "activateLabelString": 357,
        "guiLabelString": 340,
        "text": 340,
        "meatLabel": 329,
        "ingestCommandString": 288,
        "ingestReportString": 288,
        "fuelLabel": 258,
        "activatingStringPending": 238,
        "activatingString": 221,
        "fuelGizmoLabel": 190,
        "outOfFuelMessage": 139,
        "notHackedInspectString": 133,
        "messageCompletedString": 119,
        "onCooldownString": 114,
        "completedLetter": 102,
        "completedLetterLabel": 102,
        "letterLabel": 85,
        "letterText": 85,
        "hackedMessage": 85,
        "invalidTargetPawn": 78,
        "hackedInspectString": 68,
        "progressedLetters.{idx}": 68,
        "messageCooldownEnded": 51,
        "progressedLetterLabel": 51,
        "repeatCompletedLetter": 51,
        "repeatCompletedLetterLabel": 51,
        "noAssignablePawnsDesc": 36,
        "labelOverride": 34,
        "tooltipOverride": 34,
        "groundSpawnerLetterLabel": 34,
        "groundSpawnerLetterText": 34,
        "letterDesc": 34,
        "letterTitle": 34,
        "cannotSealLabel": 26,
        "confirmSealText": 26,
        "sealCommandDesc": 26,
        "sealCommandLabel": 26,
        "offMessage": 24,
        "ingestReportStringEat": 24,
        "inspectStringLabel": 19,
        "countdownLabel": 19,
        "enoughPlantsLetterLabel": 19,
        "enoughPlantsLetterText": 19,
        "message": 19,
        "reportText": 19,
        "statLabel": 19,
        "destroyedLetterLabel": 17,
        "destroyedLetterText": 17,
        "hackedLetterLabel": 17,
        "hackedLetterText": 17,
        "letterDoorOpenedLabel": 17,
        "letterDoorOpenedText": 17,
        "letterTurretDisabledLabel": 17,
        "letterTurretDisabledText": 17,
        "letterTurretHackedLabel": 17,
        "letterTurretHackedText": 17,
        "messageNoValidTarget": 17,
        "activeInspectString": 17,
        "crashedLetterLabel": 17,
        "crashedLetterText": 17,
        "destabilizationInspectString": 17,
        "destabilizationMessage": 17,
        "cooldownEndedMessage": 17,
        "messageActivating": 17,
        "capturedLetterLabel": 17,
        "capturedLetterText": 17,
        "useMessage": 17,
        "simpleAnimalLabel": 17,
        "digestingInspector": 17,
        "messageDigested": 17,
        "messageDigestionCompleted": 17,
        "messageEmerged": 17,
        "messageEmergedCorpse": 17,
        "becomingUnstableInspectText": 17,
        "departingMessage": 17,
        "leftLetterLabel": 17,
        "leftLetterText": 17,
        "onslaughtEndedMessage": 17,
        "onslaughtInspectText": 17,
        "unstableInspectText": 17,
        "unstableWarning": 17,
        "triggeredMessage": 16,
        "autohackWarningString": 16,
        "enteredLetterLabel": 16,
        "enteredLetterText": 16,
        "cannotEnterLabel": 13,
        "sealedInspectString": 13,
        "completedLetterText": 6,
        "completedLetterTitle": 6,
        "letterDeactivatedAppend": 4,
        "letterDeactivatedDesc": 4,
        "letterDeactivatedLabel": 4
    },
    "MonolithLevelDef": {
        "monolithLabel": 119,
        "levelInspectText": 102,
        "extraQuestDescription": 68,
        "activateFloatMenuText": 51,
        "activateGizmoDescription": 51,
        "activateGizmoText": 51,
        "activateQuestText": 51,
        "monolithCanBeActivatedText": 51,
        "pawnSentToActivateMessage": 51,
        "activatedLetterText": 51,
        "activatableLetterLabel": 34,
        "activatableLetterText": 34,
        "monolithDescription": 17
    },
    "GeneDef": {
        "symbol": 9945,
        "labelShortAdj": 1130,
        "customEffectDescriptions.{idx}": 238,
        "resourceLabel": 34,
        "resourceDescription": 17
    },
    "BodyDef": {
        "customLabel": 13939
    },
    "WorkGiverDef": {
        "gerund": 3437,
        "verb": 3437
    },
    "StatDef": {
        "formatString": 461,
        "labelForFullStatList": 382,
        "customLabel": 128,
        "formatStringUnfinalized": 61,
        "offsetLabel": 17,
        "statFactorsExplanationHeader": 10
    },
    "RitualPatternDef": {
        "ritualExpectedDesc": 228,
        "descOverride": 171,
        "shortDescOverride": 171,
        "ritualExpectedDescNoAdjective": 36,
        "beginRitualOverride": 34,
        "ritualExpectedPostfix": 26,
        "ritualExplanation": 19
    },
    "CreepJoinerDownsideDef": {
        "letterLabel": 3
    },
    "LandingOutcomeDef": {
        "letterLabel": 72,
        "letterText": 72
    },
    "PawnsArrivalModeDef": {
        "textEnemy": 272,
        "textWillArrive": 272,
        "textFriendly": 212
    },
    "BodyPartGroupDef": {
        "labelShort": 468
    },
    "JobDef": {
        "reportString": 7048
    },
    "IdeoPresetCategoryDef": {
        "groupLabel": 114
    },
    "MutantDef": {
        "labelNoLocation": 68,
        "debugLabel": 34,
        "deathLetter": 17,
        "deathLetterExtra": 17,
        "namePrefix": 17
    },
    "InstructionDef": {
        "text": 890,
        "rejectInputMessage": 745,
        "onMapInstruction": 408,
        "textController": 220
    },
    "ThoughtDef": {
        "labelSocial": 239,
        "labelInBracketsExtraForHediff": 68
    },
    "InspirationDef": {
        "baseInspectLine": 200,
        "beginLetter": 200,
        "endMessage": 192,
        "beginLetterLabel": 72
    },
    "BossgroupDef": {
        "leaderDescription": 51
    },
    "SurgeryOutcomeEffectDef": {
        "letterLabel": 154,
        "letterText": 154
    },
    "ConceptDef": {
        "helpText": 1970,
        "helpTextController": 242
    },
    "RoyalTitleDef": {
        "labelFemale": 141
    },
    "RitualOutcomeEffectDef": {
        "potentialExtraOutcomeDesc": 418,
        "extraPredictedOutcomeDescriptions.{idx}": 209,
        "labelAbstract": 186,
        "expectedThingLabelTip": 133,
        "extraInfoLines.{idx}": 19,
        "labelNotMet": 17
    },
    "PlaceDef": {
        "rulesStrings": 380
    },
    "RulePackDef": {
        "rulesStrings": 5786,
        "rulesStrings.{idx}": 185,
        "rulesFiles": 171
    },
    "RecipeDef": {
        "jobString": 4864,
        "customSummary": 320,
        "successfullyRemovedHediffMessage": 193
    }
}
def get_translatable_fields2(deftype:str):
    """Get the translatable fields for a given def type."""
    res = DEFAULT.copy()
    for t,v in records.get(deftype, {}).items():
        if "{idx}" in t:
            t = t.replace(".{idx}", "")  # Remove the index for easier comparison
            res[t] = res.setdefault(t, 0)+v
        else:
            res[t] = v
    return res

def get_translatable_fields(deftype:str) -> dict[str, int]:
    """Get the translatable fields for a given def type."""
    return records.get(deftype, {})|DEFAULT

def find_translatable_fields_from_definjected(root_dir:Path, skip_common=True) -> dict[str, Counter]:
    from core.engines.rimworld.extractor import load_xml_file
    results = {}
    for xml_file in root_dir.rglob("*.xml"):
        def_type = xml_file.relative_to(root_dir).parent.name
        if def_type == 'TipSetDef':
            continue
        lang_data:dict[str, Any] = load_xml_file(xml_file)
        keys = []
        for k in lang_data.keys():
            if not isinstance(k,(str, int)): # skip comments
                continue
            last_part = k.split(".")[-1]
            # if last_part is an integer:
            if last_part.isdigit():
                last_part = k.split(".")[-2]+".{idx}"
            if last_part == "resourceDescription":
                pass
            if skip_common and last_part in DEFAULT:
                continue
            keys.append(last_part)
                
        if (c := Counter(keys)):
            if def_type not in results:
                results[def_type] = c
            else:
                results[def_type]+= c
    return results
def merge_records(records1:dict[str, Counter], records2: dict[str, Counter]) -> dict[str, Counter]:
    """Merge two records dictionaries, summing the counts for each tag."""
    merged = {}
    all_keys = set(records1.keys()).union(records2.keys())
    for key in all_keys:
        counter1 = records1.get(key, Counter())
        counter2 = records2.get(key, Counter())
        merged[key] = counter1 + counter2
    return merged
def get_records(path:Path, skip_common:bool=True) -> dict[str, Counter]:
    summary = {}
    for DLC in ["Core", "Ideology", "Royalty", "Biotech", "Odyssey", "Anomaly"]:
        root = path/DLC/"DefInjected"
        results = find_translatable_fields_from_definjected(root, skip_common=skip_common)
        summary = merge_records(summary, results)
    return summary
if __name__ == "__main__":
    import json
    summary = {}
    # root = Path("your/Path/to/translations")
    root = Path.home()/"Desktop"/"Project/Rimworld/Ludeon"
    for dirpath in root.iterdir():
        try:
            if dirpath.is_dir() and dirpath.name.startswith("RimWorld"):
                records = get_records(dirpath, skip_common=False)
                summary = merge_records(summary, records)
        except Exception as e:
            print(f"Error processing {dirpath}: {e}")

    summary = {k: dict(sorted(v.items(), key=lambda item: item[1], reverse=True)) for k, v in summary.items()}
    print(json.dumps(summary, indent=4, ensure_ascii=False, default=list))