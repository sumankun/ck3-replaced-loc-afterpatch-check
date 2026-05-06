What it does
------------
The program takes all localization keys from your mod folder and compares those same keys
between old vanilla and new vanilla.

How to use
------------
1. Run ck3_loc_checker.exe (if you dont build your own exe file, downloading only exe file is enough)
2. Select your mod localization folder.
3. Select the old vanilla localization folder.
4. Select the new vanilla localization folder.
5. Click "Check and open report".

Recommended folder choices as an example:
- mod/localization/replace/english
- old_vanilla_path/localization/english
- new_vanilla_path/localization/english

The program recursively reads all .yml files below the selected folder.

Building the exe yourself in case you dont trust my exe file
-------------------------
pip install pyinstaller

Then run this file in the program folder:
build_exe.bat
The exe will appear in:
dist/ck3_loc_checker.exe
