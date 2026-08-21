<icecast>
    <location>__LOCATION__</location>
    <admin>admin@localhost</admin>

    <limits>
        <clients>50</clients>
        <sources>2</sources>
        <queue-size>524288</queue-size>
        <client-timeout>30</client-timeout>
        <header-timeout>15</header-timeout>
        <source-timeout>10</source-timeout>
        <burst-size>65535</burst-size>
    </limits>

    <authentication>
        <source-password>__SOURCE_PASSWORD__</source-password>
        <relay-password>__RELAY_PASSWORD__</relay-password>
        <admin-user>admin</admin-user>
        <admin-password>__ADMIN_PASSWORD__</admin-password>
    </authentication>

    <hostname>__HOSTNAME__</hostname>
    <listen-socket>
        <port>__PORT__</port>
        <bind-address>127.0.0.1</bind-address>
    </listen-socket>

    <mount type="normal">
        <mount-name>__MOUNT__</mount-name>
        <public>0</public>
    </mount>

    <fileserve>1</fileserve>

    <paths>
        <basedir>/usr/share/icecast2</basedir>
        <logdir>/var/log/icecast2</logdir>
        <webroot>/usr/share/icecast2/web</webroot>
        <adminroot>/usr/share/icecast2/admin</adminroot>
        <alias source="/" destination="/status.xsl"/>
    </paths>

    <logging>
        <accesslog>access.log</accesslog>
        <errorlog>error.log</errorlog>
        <loglevel>3</loglevel>
        <logsize>10000</logsize>
    </logging>

    <security>
        <chroot>0</chroot>
        <changeowner>
            <user>icecast2</user>
            <group>icecast</group>
        </changeowner>
    </security>
</icecast>
