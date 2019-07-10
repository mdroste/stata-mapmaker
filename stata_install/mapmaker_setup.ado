program define mapmaker_setup
	version 16

	* Create directories, if they don't exist already
	cap mkdir "`c(sysdir_personal)'"
	cap mkdir "`c(sysdir_personal)'mapmaker"
	
	* Store current working directory
	local old_dir = "`c(pwd)'"

	* Change directory to mapmaker directory
	cd "`c(sysdir_personal)'mapmaker"

	* Copy file from github to mapmaker
	di "Downloading latest mapmaker source from Github..."
	cap rm src.zip
	copy https://raw.githubusercontent.com/mdroste/stata-mapmaker/master/src.zip src.zip
	
	* Unzip file
	di "Unzipping mapmaker files to `c(sysdir_personal)'mapmaker"
	unzipfile src.zip, replace

	* If not on Windows, try to set permissions for mac.phantomjs
	if "`c(os)'"!="Windows" {
		di "Windows not detected, trying to set permissions"
		cd "`c(sysdir_personal)'mapmaker/bin"
		!chmod 777 mac.phantomjs
	}

	* Change back to original directory
	cd "`old_dir'"
	di "Done!"

end
