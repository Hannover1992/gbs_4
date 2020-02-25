#include <stdio.h>
#include "plist.h"
#include <unistd.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <string.h>

//wd stands for working directory. It is necessary that it is public because getwd() and run need the wd.
char* wd;
//added fun with colors!
char* colors[] = {"\x1B[0m", "\x1B[31m", "\x1B[32m", "\x1B[33m", "\x1B[34m", "\x1B[35m", "\x1B[36m"};
//It is necessary that buffer_size is public because the functions run and parsing_arguments need it.
//parsing_arguments only needs ist for checking the last sign.
int buffer_size;

//executing the given arguments.
void execute(char* arguments[], int AMOUNT_OF_ARGUMENTS, int sleep, char* cmd_cpy)
{
    if (arguments == NULL)
    {
        fprintf(stderr, "%s\n", wd);
        return;
    }
    else
    {
        pid_t child_pid;
        int wstatus;
        child_pid = fork();
        if (child_pid == -1)
        {
            perror("ERROR");
            exit(EXIT_FAILURE);
        }
        if (child_pid == 0)
        {
        // Code executed by child

            if (execvp(arguments[0], arguments) < 0) {
                //execvp failed
                perror("ERROR");
                exit(EXIT_FAILURE);
            }
            else
            {
                //execvp success (no error)
                exit(EXIT_SUCCESS);
            }
        }
        else
        {
            if(sleep)
            {
                //if sleep insertlist (running in background)
                insertElement(child_pid, cmd_cpy);
            }
            else
            {
                // Code executed by parent
                waitpid(child_pid, &wstatus, 0);
                // Waiting for the children
                fprintf(stderr, "\x1B[31mExitstatus [%s] = %d\n", cmd_cpy, WEXITSTATUS(wstatus));
                //printing "wexitstatus"
            }
        }
    }
}

//refreshes the working directory.
void getwd()
{
    //PATH_MAX from limits.h
    wd = getcwd(wd, PATH_MAX);
    if(wd == NULL)
    {
        perror("Memory allocation failed!\n");
    }
}

//changing the directory to the given path
void cd(char* dir)
{
    if(chdir(dir) != 0)
    {
        fprintf(stderr, "%s\n", dir);
    }
    else
    {
        //chdir(dir)
        fprintf(stderr, "%s\n", dir);
    }
}

//iterating through the list and printing the running jobs.
int walk_jobs(pid_t zombie_pid, const char* command)
{
    //int w_status;
    //waitpid(zombie_pid, &w_status, WNOHANG);
		fprintf(stdout, "\x1B[34m[%d] %s\n", zombie_pid, command);
    return 0;
}

//parsing the arguments and calls the proper execution.
void parsing_arguments(char* cmd)
{
    char cmd_cpy[strlen(cmd)];
    strcpy(cmd_cpy, cmd);
    int sleep = 0;
    //argument too long!
    if(cmd[buffer_size] != 0)
    {
        return;
    }
    //it is a job!
    if(cmd[strlen(cmd) - 1] == '&')
    {
        cmd = strtok(cmd, "&");
        sleep = 1;
    }
    //list the jobs!
    if(strcmp(cmd, "jobs") == 0)
    {
        walkList(walk_jobs);
        return;
    }

    char* args[127];
    //127 because i found it on google and sysconf(_SC_ARG_MAX) didn't work
    //Splitting the input after every " " or " \t"
  	char* part = strtok(cmd, " \t");
    args[0] = part;
    int i = 0;

    while(part != NULL)
    {
  	   part = strtok(NULL, " \t");
  	   args[++i] = part;
    }
    //The argument is cd. Change directory!
    if (strcmp(args[0], "cd") == 0)
    {
        cd(args[1]);
        getwd();
        return;
    }
    //otherwise it will just be executed
    execute(args, i, sleep, cmd_cpy);
}



int print_sleep(pid_t zombie_pid, const char* command)
{
    int w_status = 0;
    waitpid(zombie_pid, &w_status, WNOHANG);
    //if (getpgid(zombie_pid) < 0) would work, too!
    if(waitpid(zombie_pid, &w_status, WNOHANG) < 0)
    {
        fprintf(stderr, "\x1B[31mExitstatus: [%s] = %d\n", command, WEXITSTATUS(w_status));
				removeElement(zombie_pid, NULL, 0);
    }
		return 0;
}


void run() {
    while(1)
    {
        int r = rand() % 6;
        //check zombie?
        walkList(print_sleep);
        //\x1B[32m
        fprintf(stderr, "%s%s: ", colors[r], wd);
        //printing in green ;)
		char* input = calloc(buffer_size+2, sizeof(input));
        if (input == NULL)
        {
            continue;
        }
		    fgets(input, buffer_size+2, stdin);
        if(input[0] == 0)
        {
            fprintf(stderr, "\n");
            free(input);
            return;
        }
        else if(input[buffer_size] != 0)
        {
            free(input);
            continue;
        }
        else if(input[0] != '\n')
        {
            parsing_arguments(strtok(input, "\n"));
        }
        else
        {
            //fprintf(stderr, "%s\n", wd);
        }

        free(input);

	  }
}



int main(void)
{
    getwd();
    buffer_size = sysconf(_SC_LINE_MAX);
    run();
}
