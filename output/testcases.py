import os
import logging
import time
import traceback
from output.enum_class import *
from output.structure_class import *
from output.python_API import *

if __name__ == "__main__":
    logging.info("Function name : hello_world")
    something = MY_BOOL.MY_TRUE.value
    try:
        hello_world(something)
    except Exception:
        traceback.print_exc()
    logging.debug(f"something = {something}")
    logging.info("\n")

