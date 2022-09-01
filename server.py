import sys
import ssl
import socket
import datetime
import threading
from threading import Lock,Thread

class SocketWrapper:
	def __init__(self,sock = None):
		if sock is None:
			self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		else:
			self.socket = sock


	def connect(self,host,port):
		try:
			self.socket.connect((host,int(port)))
			return True
		except socket.error:
			return False

	def close(self):
		# close the socket connection
		self.socket.close()

	def send(self,data):
		bytes_sent = 0
		msg_len = len(data)
		while bytes_sent < msg_len:
			sent = self.socket.send(data[bytes_sent:])
			bytes_sent += sent

	def receive(self):
		chunks = []
		self.socket.settimeout(0.5)
		while True:
			try:
				chunk = self.socket.recv(4096)
				if(chunk == b''):
					break
				chunks.append(chunk)
			except socket.error:
				self.socket.settimeout(0)
				break;

		return b''.join(chunks)



class Server():

	def __init__(self,host='localhost',port = 1000):
		# normal Ctrl+C doesn't work on windows for some weird reason
		self.port = port 
		self.host = host
		self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM) 
		self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		self.socket.bind((self.host,self.port));
		self.socket.listen(5)
		self.running = True;
		print("Https proxy at",self.host,self.port)

	def parseHeaders(self,requestHeader):
		# Convert the header to key-value pairs
		headers = {}

		for header in requestHeader:
			i = header.find(':')
			headers[header[:i].lower()] = header[i+1:].strip()
		return headers;

	def generateRequest(self,requestUrl,requestHeader,requestBody):
		# reconstruct the request to send
		method,url,version = requestUrl.split(' ')
		i = url.find('://')
		if(i != -1):
			url = url[i+3:]
			i = url.find('/')
			if i == -1:
				url = "/"
			else:
				url = url[i:]
		else:
			# insurance
			url = url

		req = f"{method} {url} {version}\r\n"
		
		for header in requestHeader:
			req += header+'\r\n'

		req += "SaveData: on\r\n"
		req += "\r\n"

		

		# the request body was already in bytes format
		return req.encode() + requestBody

	def parseRequest(self,clientConnection):

		request = clientConnection.recv(4096 * 16) # just setting it high
		if(request == b''):
			self.closeConnection(clientConnection)
			return
		
		request = request.split(b"\r\n\r\n")
		request[0] = request[0].decode()
		requestHeader,requestBody = request
		# get remote request destination
		requestHeader = requestHeader.split('\r\n')
		requestUrl = requestHeader.pop(0)

		requestMethod,requestPath,_ = requestUrl.split(' ')

		headers = self.parseHeaders(requestHeader)

		if(requestMethod == "CONNECT"):
			self.handleHttps(clientConnection,requestUrl)
			print(f"[{datetime.datetime.now()}][TUNNELING] {requestPath}")
			return

		print(f"[{datetime.datetime.now()}] {requestUrl}")



		
		hostString = headers['host']
		

		# get hostname and port from header's host field
		if(hostString.find(':') != -1):
			remoteHost,remotePort = hostString.split(':')
			remotePort = int(remotePort)
		else:
			remoteHost = hostString 
			remotePort = 80


		request = self.generateRequest(requestUrl,requestHeader,requestBody)

		self.handleHttp(request,clientConnection,(remoteHost,remotePort))

	def handleHttps(self,connection,requestUrl):
		try:
			method,uri,version = requestUrl.split(' ')
		except Exception as e:
			print(meta);
			return
		host,port = uri.split(':')
		address = (host,port)
		clientSocket = SocketWrapper(connection)

		serverSocket = SocketWrapper()
		# if connection to the remote server is created successfuly
		if(serverSocket.connect(host,port)):
			# send connection success message to the client
			clientSocket.send(b'HTTP/1.1 200 OK\r\n\r\n');
			
			while True:
				try:	
					clientResponse = clientSocket.receive()
					if(clientResponse == b''):
						print("breaking connection (client)",host)
						break
					serverSocket.send(clientResponse)	
					print("Sent client - server",address)
					serverResponse = serverSocket.receive()
					if(serverResponse == b''):
						print("breaking connection (server)",host)
						break
					clientSocket.send(serverResponse)
					print("Sent server - client",address)
				except socket.error:
					break;
		else:
			# send someking of error. In this case 502
			clientSocket.send(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
		# close the connection
		clientSocket.close()
		serverSocket.close()


	def handleHttp(self,req,connection,address):
		host,port = address
		clientSocket = SocketWrapper(connection)

		serverSocket = SocketWrapper()
		# if connection to the remote server is created successfuly
		if(serverSocket.connect(host,port)):
			serverSocket.send(req)	
			serverResponse = serverSocket.receive()
			clientSocket.send(serverResponse)
		else:
			# send someking of error. In this case 502
			clientSocket.send(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')

		# close the connection
		clientSocket.close()
		serverSocket.close()

	def closeConnection(self,connection):
		connection.shutdown(socket.SHUT_RDWR)
		connection.close()


	def mainloop(self):
		while(self.running):
			connection,address = self.socket.accept()
			# self.parseRequest(connection)
			# self.handleClientRequest(connection)
			t = Thread(target=self.parseRequest,args=(connection,))
			t.daemon = True
			t.start()



Server().mainloop()