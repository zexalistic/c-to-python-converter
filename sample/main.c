#include "main.h"
#include <stdio.h>

FUNC_PREFIX MY_INT hello_world(MY_BOOL something) {
	printf("hello, world\n");
	return 0;
}

int main() {
	MY_BOOL something = MY_TRUE;
	hello_world(something);
}