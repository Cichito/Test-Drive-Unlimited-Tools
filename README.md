# Test-Drive-Unlimited-Tools
A set of tools built with Python that work on both TDU1 and TDU2 using external libraries like [FFmeg](https://ffmpeg.org/download.html) and other programs like [TDUMT2](https://github.com/djey47/tdumt2) by DJey47.

## TDU Universal Audio Editor
TDU Universal Audio Editor it's a program for importing your audio files and converting them to a specific format that Test Drive can recognize. It was originally developed for TDU1, which has a problem with a lot of software having trouble finding the right compatibility. The [FFmeg](https://ffmpeg.org/download.html) library comes already preinstalled so no need to download anything external.

### How to use
The program is simple to use, just start it with any development tool having Python installed on your computer, you need to select an audio file and decide which format it should be exported in, for TDU1 the basic formats are wav with the `mono` channel in most files and `stereo` in other cases, the  `wav ` type must be `IMA ADPCM` with `4 bit` depth, the sample rate must be `44100Hz` and the bitrate must be `177 kbps`. The tdu2 files are similar to those of tdu1 but have small differences and are less important.

## TDU Multi Unpaker
TDU Multi Unpaker use the program made by [DJey47](https://github.com/djey47) implement a script that automatically reads all the BNKs in the EURO folder and convert them all to a specific folder of your choice. 

# BEFORE USING IT! Read!
This tool is still a work in progress and it is very likely that it will suddenly stop working or not work at all. So be very careful.

## How to use the TDU Multi Unpaker 
As TDU Universal Audio Editor start any development tool and run it. First you need to select the folder where you can download MiniBnkManager.exe [here](https://github.com/djey47/tdumt2),after select the folder where the bnk files are located (you can select the EURO folder directly if you want to unpack all the bnk) the program will read all the .bnk files even in the subfolders, finally select the folder where all the files must be extracted, I recommend to select the default folder of MiniBnkManager is usually the folder named work.

## Speeds
-  `Safe` slow asf but as the name suggest it was made to prefent errors
-  `Fast ` normal speed but with decent speed
-  `Turbo ` really unsafe but it will get the job done in less than 1 hour (if you want to unpack the entire game)

## Position Config
By selecting the Configure Options button, the program will open a window that will record the current cursor position. This is used to select the important points of the MiniBnkManager. Follow the instructions carefully. Test first with a single  `BNK ` file to be sure.

## Test position
By clicking on the test positions button, the program will emulate the mouse movements that the program will perform to verify whether it is actually following the correct positioning of the cursor.

## Verify Extraction
It will check if all the bnk files are present in the destination folder and if they are missing it will write them to a log.

## Logs
Both scripts generate detailed log files that can be useful for identifying any errors or missing files.

