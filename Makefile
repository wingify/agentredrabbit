all: build

runtests:
	nosetests -v --verbosity=3

build: runtests
	python setup.py build
	python setup.py sdist

docs: clean
	epydoc --config docs/epydoc.cfg
	echo "Docs built in docs/agentredrabbit"

clean:
	rm -frv build dist *egg-info docs/agentredrabbit/

install: clean
	python setup.py sdist
	pip install dist/agentredrabbit-*.tar.gz
	cp init.d/agentredrabbit /etc/init.d
	chmod +x /etc/init.d/agentredrabbit
	update-rc.d -f agentredrabbit defaults
	chown www-data:www-data /var/log/agentredrabbit.log
	chown www-data:www-data /var/lib/agentredrabbit.dump

sample-setup:
	rabbitmqctl add_user agentredrabbit rabbitpassword
	rabbitmqctl set_user_tags agentredrabbit administrator
	rabbitmqctl add_vhost /rabbitvhost
	rabbitmqctl set_permissions -p /rabbitvhost agentredrabbit ".*" ".*" ".*"
