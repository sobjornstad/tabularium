all: editDistanceLibrary

editDistanceLibrary: distlib/distlib_64.so

distlib/distlib_64.so: distlib/distlib_64.dll
	chmod 755 distlib/linux_build_extensions.sh
	cd distlib && ./linux_build_extensions.sh

distlib/distlib_64.dll:
	git clone https://github.com/schiffma/distlib.git distlib