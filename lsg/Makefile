CFLAGS  = -std=c11 -pedantic -D_XOPEN_SOURCE=700 -Wall -Werror
LDFLAGS =
CC		= gcc
.PHONY: all doc clean

all: clash

clash: clash.o plist.o plist_walklist.o
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ -c $^

clean:
	$(RM) clash *.o

test:
	python3 tests/unittest.py -t tests

copy_tests: tests
	if [ "" = "${DST}" ]; then exit 1; fi
	cp -rf tests Makefile ${DST}/

.PHONY: clean test copy_tests

