#pragma once

/*
	This is a sample file to show the function of our Ctypes wrapper
	All comments will be ignored.
*/

# include "sample.h"

// We can parse either hello_world or hello_world_2 depending on whether you set func_header in config.json 
FUNC_PREFIX MY_INT hello_world(MY_BOOL something);
MY_INT hello_world_2(MY_BOOL something);