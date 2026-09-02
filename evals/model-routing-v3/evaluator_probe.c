#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static int emit(int error_number) {
    const char *category = "other_error";
    int result = 1;
    if (error_number == 0) {
        category = "success";
        result = 0;
    } else if (error_number == EPERM || error_number == EACCES) {
        category = "policy_denied";
        result = 77;
    }
    printf("{\"category\":\"%s\",\"errno\":%d}\n", category, error_number);
    return result;
}

static int read_target(const char *path) {
    int descriptor = open(path, O_RDONLY);
    if (descriptor < 0) {
        return emit(errno);
    }
    unsigned char value = 0;
    if (read(descriptor, &value, sizeof(value)) < 0) {
        int error_number = errno;
        close(descriptor);
        return emit(error_number);
    }
    close(descriptor);
    return emit(0);
}

static int write_target(const char *path) {
    int descriptor = open(path, O_WRONLY);
    if (descriptor < 0) {
        return emit(errno);
    }
    close(descriptor);
    return emit(0);
}

static int connect_localhost(void) {
    int descriptor = socket(AF_INET, SOCK_STREAM, 0);
    if (descriptor < 0) {
        return emit(errno);
    }
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(443);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    int result = connect(descriptor, (struct sockaddr *)&address, sizeof(address));
    int error_number = result == 0 ? 0 : errno;
    close(descriptor);
    return emit(error_number);
}

static int connect_localhost6(void) {
    int descriptor = socket(AF_INET6, SOCK_STREAM, 0);
    if (descriptor < 0) {
        return emit(errno);
    }
    struct sockaddr_in6 address;
    memset(&address, 0, sizeof(address));
    address.sin6_family = AF_INET6;
    address.sin6_port = htons(443);
    address.sin6_addr = in6addr_loopback;
    int result = connect(descriptor, (struct sockaddr *)&address, sizeof(address));
    int error_number = result == 0 ? 0 : errno;
    close(descriptor);
    return emit(error_number);
}

static int connect_other_port(void) {
    int descriptor = socket(AF_INET, SOCK_STREAM, 0);
    if (descriptor < 0) {
        return emit(errno);
    }
    struct sockaddr_in address;
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(80);
    if (inet_pton(AF_INET, "192.0.2.1", &address.sin_addr) != 1) {
        close(descriptor);
        return emit(EINVAL);
    }
    int result = connect(descriptor, (struct sockaddr *)&address, sizeof(address));
    int error_number = result == 0 ? 0 : errno;
    close(descriptor);
    return emit(error_number);
}

static int connect_unix(const char *path) {
    int descriptor = socket(AF_UNIX, SOCK_STREAM, 0);
    if (descriptor < 0) {
        return emit(errno);
    }
    struct sockaddr_un address;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    if (strlen(path) >= sizeof(address.sun_path)) {
        close(descriptor);
        return emit(ENAMETOOLONG);
    }
    strcpy(address.sun_path, path);
    int result = connect(descriptor, (struct sockaddr *)&address, sizeof(address));
    int error_number = result == 0 ? 0 : errno;
    close(descriptor);
    return emit(error_number);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        return emit(EINVAL);
    }
    if (strcmp(argv[1], "read") == 0 && argc == 3) {
        return read_target(argv[2]);
    }
    if (strcmp(argv[1], "write") == 0 && argc == 3) {
        return write_target(argv[2]);
    }
    if (strcmp(argv[1], "connect-localhost") == 0 && argc == 2) {
        return connect_localhost();
    }
    if (strcmp(argv[1], "connect-localhost6") == 0 && argc == 2) {
        return connect_localhost6();
    }
    if (strcmp(argv[1], "connect-other-port") == 0 && argc == 2) {
        return connect_other_port();
    }
    if (strcmp(argv[1], "connect-unix") == 0 && argc == 3) {
        return connect_unix(argv[2]);
    }
    return emit(EINVAL);
}
