import configparser
import winreg
import subprocess
import os.path
import json
import shutil

import test_lib

def GeneratePak(outputPakFileDir, targetPackagePathRootDir, longPackageName,  inShouldPackTo64KB = False):
    pakCmdTemplate = '"{}" "{}" {} "{}" {}'
    urealPakToolPath = test_lib.GetUnrealPakToolPath()

    outputPakFileDir = os.path.normpath(outputPakFileDir)
    targetPackagePathRootDir = os.path.normpath(targetPackagePathRootDir)

    filesToWrite = ""
    filesToWrite = longPackageName.replace('/Game', "" )
    filesToWrite = os.path.normpath(targetPackagePathRootDir + filesToWrite)
    filesToWrite = filesToWrite + '.*'

    pakFilename = test_lib.GetSha1OfLongPackageName(longPackageName)
    outputPakFilePath = os.path.join(outputPakFileDir, pakFilename + ".pak")
    dummyPackagePath = os.path.join(targetPackagePathRootDir, "dummy.uasset")
    
    if inShouldPackTo64KB:
        packDataFilePath = os.path.join(targetPackagePathRootDir, "pack_data.dat")
        if not os.path.exists(packDataFilePath):
            shutil.copy('.\\pack_data.dat', targetPackagePathRootDir)
        packDataFilepath = '"{}"'.format(os.path.join(targetPackagePathRootDir, "pack_data.dat"))
    else:
        packDataFilepath = ''

    pakCmd = pakCmdTemplate.format(urealPakToolPath, outputPakFilePath, filesToWrite, dummyPackagePath, packDataFilepath)
    subprocess.check_call(pakCmd, shell=True)

    return outputPakFilePath

if __name__ == "__main__":
    
    contentProviderProjectCookedContentDir= os.path.join(
        test_lib.GetContentProviderProjectRootDir(), "Saved\\Cooked\\WindowsNoEditor\\" +
        test_lib.GetContentProviderProjectName() + "\\Content\\")

    tempDir =  os.path.abspath(os.path.join(test_lib.GetContentProviderProjectRootDir(), "Saved\\ProjectUtils\\Temp\\"))
    tempDirPendingDelete =  os.path.abspath(os.path.join(test_lib.GetContentProviderProjectRootDir(), "Saved\\ProjectUtils\\Temp_pending_delete\\"))

    #Because deleting files is an asynchoronus operation, here is a trick to 
    # avoid this side effect.
    if os.path.exists(tempDir):
        os.rename(tempDir, tempDirPendingDelete)
        shutil.rmtree(tempDirPendingDelete)
    
    # Create project util saved dir.
    projectUtilsDir = os.path.join(test_lib.GetContentProviderProjectRootDir(), "Saved\\ProjectUtils\\")
    if not os.path.exists(projectUtilsDir):
        os.makedirs(projectUtilsDir)

    os.mkdir(tempDir)

    generatePakLogFilepath = os.path.abspath(os.path.join(test_lib.GetContentProviderProjectRootDir(), "Saved\\ProjectUtils\\GeneratePaks.log"))
    assetDependenciesFileFilpath =   os.path.abspath(os.path.join(test_lib.GetContentProviderProjectRootDir(), "Saved\\ExportAssetDependecies\\AssetDependencies.json"))

    if not os.path.exists(projectUtilsDir):
        os.mkdir(projectUtilsDir) 

    with open(generatePakLogFilepath, 'w') as generatePakLogFileHandle:
        with open(assetDependenciesFileFilpath, 'r') as assetDependenciesFileHandle:
            data = json.load(assetDependenciesFileHandle)
            for (targetPackage,dependentData) in  data.items():
                sha1OfLongTargetPackageName = test_lib.GetSha1OfLongPackageName(targetPackage)

                # Now just handle dependencies in game content dir.
                packagesToHandle = dependentData['DependenciesInGameContentDir']
                packagesToHandle.append(targetPackage)

                # Make output dir with sha1 value 
                targetOutputDir = os.path.join(tempDir, sha1OfLongTargetPackageName)
                os.mkdir(targetOutputDir)

                # Fill json object and generate pak.
                jsonObject = {}
                jsonObject["long_package_name"] = targetPackage
                jsonObject["dependent_pak_file_list"] = []
                for longPackageName in packagesToHandle:
                    outputPakFilePath = GeneratePak(targetOutputDir, contentProviderProjectCookedContentDir, longPackageName)
                    # If the pak file size is less than 64KB, when pack and regenerate pak file to meet the PAK_PRECAHCE_GRUNULARITY. 
                    if os.path.getsize(outputPakFilePath) < 64 * 1024:
                        os.remove(outputPakFilePath)
                        outputPakFilePath = GeneratePak(targetOutputDir, contentProviderProjectCookedContentDir, longPackageName,  inShouldPackTo64KB = True)
                        isPacked = True       
                    else:
                        isPacked = False
                    _, outputFilename = os.path.split(outputPakFilePath) 

                    if longPackageName != targetPackage:
                        # Self 
                        entry = {}
                        entry["file_name"] = outputFilename
                        entry["file_size"] = os.path.getsize(outputPakFilePath)
                        entry["long_package_name"] = longPackageName
                        entry["is_packed_to_64KB"] = isPacked
                        jsonObject["dependent_pak_file_list"].append(entry)
                    else:
                        # Dependencies
                        filename = longPackageName.replace('/Game', "" )
                        filename = os.path.normpath(contentProviderProjectCookedContentDir + filename)
                        jsonObject["file_size"] = os.path.getsize(outputPakFilePath)
                        jsonObject["pak_file"] = outputFilename
                        jsonObject["is_packed_to_64KB"] = isPacked
                        jsonObject["is_level"] = os.path.exists(filename + ".umap")

                        # Write json object to info file.
                        generatePakLogFileHandle.write('"{}" --> "{}"\n'.format(longPackageName, sha1OfLongTargetPackageName ))

                outputInfoFilepath = os.path.join(targetOutputDir, '{}.json'.format(sha1OfLongTargetPackageName))
                with open(outputInfoFilepath, 'w') as outputInfoFileHandle:
                    outputInfoFileHandle.write(json.dumps(jsonObject, indent=4))
                    