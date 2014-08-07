all: build

runtests:
	python setup.py test

build: runtests
	python setup.py build
	python setup.py sdist

docs: clean
	epydoc --config docs/epydoc.cfg
	echo "Docs built in docs/agentredrabbit"

clean:
	find . | grep pyc$ | xargs rm -f
	rm -frv build dist *egg-info docs/agentredrabbit/

install: clean
	python setup.py sdist
	pip install dist/agentredrabbit-*.tar.gz
	cp init.d/agentredrabbit /etc/init.d
	chmod +x /etc/init.d/agentredrabbit
	update-rc.d -f agentredrabbit defaults
	touch /var/log/agentredrabbit.log
	chown www-data:www-data /var/log/agentredrabbit.log
	python -c "import os, pickle; print pickle.dump({}, open('/var/lib/agentredrabbit.dump', 'wb')) if not os.path.exists('/var/lib/agentredrabbit.dump') else 'dump exists'"
	chown www-data:www-data /var/lib/agentredrabbit.dump

sample-setup:
	rabbitmqctl add_user agentredrabbit rabbitpassword
	rabbitmqctl set_user_tags agentredrabbit administrator
	rabbitmqctl add_vhost /rabbitvhost
	rabbitmqctl set_permissions -p /rabbitvhost agentredrabbit ".*" ".*" ".*"
