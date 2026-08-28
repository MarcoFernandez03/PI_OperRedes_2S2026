#include <linux/kernel.h>
#include <linux/syscalls.h>
#include <linux/uaccess.h>
#include <linux/socket.h>
#include <linux/in.h>
#include <linux/net.h>
#include <net/sock.h>
#include <linux/slab.h>

SYSCALL_DEFINE4(send_sensor_data, const void __user *, buf, size_t, len,
                __u32, dest_ip, __u16, dest_port)
{
	struct socket *sock;
	struct sockaddr_in addr;
	struct msghdr msg;
	struct kvec vec;
	void *kbuf;
	int ret;

	if (len == 0 || len > 4096)
		return -EINVAL;

	kbuf = kmalloc(len, GFP_KERNEL);
	if (!kbuf)
		return -ENOMEM;

	if (copy_from_user(kbuf, buf, len)) {
		kfree(kbuf);
		return -EFAULT;
	}

	ret = sock_create_kern(&init_net, AF_INET, SOCK_DGRAM, IPPROTO_UDP, &sock);
	if (ret < 0) {
		kfree(kbuf);
		return ret;
	}

	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(dest_ip);
	addr.sin_port = htons(dest_port);

	vec.iov_base = kbuf;
	vec.iov_len = len;

	memset(&msg, 0, sizeof(msg));
	msg.msg_name = &addr;
	msg.msg_namelen = sizeof(addr);

	ret = kernel_sendmsg(sock, &msg, &vec, 1, len);

	sock_release(sock);
	kfree(kbuf);

	return ret;
}