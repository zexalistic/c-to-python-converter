#pragma once
/*   
	This is a sample file to show the function of our Ctypes wrapper
	All comments will be ignored.
*/   

#define MAX 128						// Parsable

#define FUNC_PREFIX __declspec(dllexport)  // This will not be parsed. You can use this macro at the beginning of functions to indicate the functions to wrap.

#define IN							// This will not be parsed

typedef int MY_INT;					// This will not be parsed, you need to write it in config.json

typedef enum {						// Parsable
	MY_TRUE = 1,
	MY_FALSE = 0
}MY_BOOL;

typedef enum{						// Parsable
	TUE,
	WED,
	THU = 2,
	FRI
}WEEKDAYS;

enum MONTHS {						// Parsable
	JAN,
	FEB
};

struct _MY_STRUCT{					// Parsable
	MY_INT a[MAX];
	MY_BOOL b;
	int* c;
};

typedef struct _MY_STRUCT MY_STRUCT;		// Parsable
typedef MY_STRUCT* MY_STRUCT_PTR;			// Parsable
typedef MY_STRUCT YOUR_STRUCT;				// This will not be parsed. We do not support nested citation.

typedef MY_INT (*MY_FUNC_PTR)(				// Parsable
	MY_BOOL a,
	MY_STRUCT_PTR p
	);

union YOUR_UNION {                            // Parsable
	int a;
	char b;
	double c;
};

typedef union _MY_UNION {					 // Parsable
	int a;
	char b;
	double c;
} MY_UNION;

typedef struct _DEV {						// Parsable
	MY_FUNC_PTR func_p;
} DEV, *DEV_PTR;

typedef struct {						   // Parsable
	MY_FUNC_PTR func_p;
} DEV2, * DEV2_PTR;

