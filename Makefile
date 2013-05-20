all: build

runtests:
	nosetests -v --verbosity=3

build: runtests
	python setup.py build
	python setup.py sdist

install: build
	pip install dist/agentredrabbit-*.tar.gz

clean:
	rm -frv build dist *egg-info

sample-setup:
	rabbitmqctl add_user agentredrabbit rabbitpassword
	rabbitmqctl set_user_tags agentredrabbit administrator
	rabbitmqctl add_vhost /rabbitvhost
	rabbitmqctl set_permissions -p /rabbitvhost agentredrabbit ".*" ".*" ".*"
