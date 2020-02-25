#include <stdlib.h>
#include <sys/types.h>
#include <string.h>

#include "plist.h"

/* Die Funktionen und Definitionen in dieser Datei bitte unveraendert lassen!
 * Falls Sie einen Bug in dieser Implementierung finden, melden Sie diesen bitte
 * an gbs@sra.uni-hannover.de.
 * Die Implementierung von walkList() ist in der plist_walklist.c vorzunehmen.
 */

struct qel {
	pid_t pid;
	char *cmdLine;
	struct qel *next;
} *head;

int insertElement(pid_t pid, const char *cmdLine) {
	struct qel *lauf = head;
	struct qel *schlepp = NULL;

	while ( lauf ) {
		if ( lauf->pid == pid ) {
			return -1;
		}

		schlepp = lauf;
		lauf = lauf->next;
	}

	lauf = malloc(sizeof(struct qel));
	if ( NULL == lauf ) { return -2; }

	lauf->cmdLine = strdup(cmdLine);
	if( NULL == lauf->cmdLine ) {
		free(lauf);
		return -2;
	}

	lauf->pid  = pid;
	lauf->next = NULL;

	/* Einhaengen des neuen Elements */
	if ( NULL == schlepp ) {
		head = lauf;
	} else {
		schlepp->next = lauf;
	}

	return pid;
}

int removeElement(pid_t pid, char *buf, size_t buflen) {
	if ( head == NULL ) {
		return -1;
	}

	struct qel* lauf = head;
	struct qel* schlepp = NULL;

	while ( lauf ) {
		if ( lauf->pid == pid ) {
			if ( NULL == schlepp ) {
				head = head->next;
			} else {
				schlepp->next = lauf->next;
			}

			strncpy(buf, lauf->cmdLine, buflen);
			if( buflen>0 ) {
				buf[buflen-1]='\0';
			}
			int retVal = strlen(lauf->cmdLine);

			/* Speicher freigeben */
			free(lauf->cmdLine);
			lauf->cmdLine = NULL;
			lauf->next = NULL;
			lauf->pid = 0;
			free(lauf);
			return retVal;
		}

		schlepp = lauf;
		lauf = lauf->next;
	}

	/* PID not found */ 
	return -1;
}
