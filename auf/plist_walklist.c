#include <stdlib.h>
#include "plist.h"

extern struct qel {
	pid_t pid;
	char *cmdLine;
	struct qel *next;
} *head;

void walkList( int (*callback) (pid_t, const char *) ) {
		struct qel* item = head;
		while(item != NULL)
		{
				int toReturn = callback(item->pid, item->cmdLine);
				if(toReturn !=0)
				{
						break;
				}
				else
				{
						item = item->next;
				}
		}
		return;
}
