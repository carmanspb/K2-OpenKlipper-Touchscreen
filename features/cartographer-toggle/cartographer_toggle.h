#ifndef CARTOGRAPHER_TOGGLE_H
#define CARTOGRAPHER_TOGGLE_H
#include "../../src/screen.h"
void cartographer_view(void);
bool cartographer_action(const char *action);
void cartographer_sent(const cJSON *request);
void cartographer_tick(void);
bool cartographer_waiting(void);
bool cartographer_screen(void);
#endif
