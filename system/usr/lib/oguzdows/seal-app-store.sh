#!/bin/sh
# PC ve Pi: yetkili dar paket yardımcısı kullanıcıya yazılabilir kalmasın.
set -eu
for path in /usr /usr/lib /usr/share /usr/local /usr/local/bin /usr/local/sbin \
    /usr/share/polkit-1 /usr/share/polkit-1/actions /usr/share/oguzdows \
    /usr/share/oguzdows/native /usr/share/oguzdows/scripts; do
    chown root:root "$path"
    chmod go-w "$path"
done
chown -R root:root /usr/lib/oguzdows /usr/share/oguzdows/native /usr/share/oguzdows/scripts
chmod -R go-w /usr/lib/oguzdows /usr/share/oguzdows/native /usr/share/oguzdows/scripts
chown root:root /usr/local/sbin/oguzdows-maintenance \
    /usr/share/polkit-1/actions/org.oguzdows.maintenance.policy
chmod 0755 /usr/local/sbin/oguzdows-maintenance
chmod 0644 /usr/share/polkit-1/actions/org.oguzdows.maintenance.policy
# Kimlik, yetkili köken / mimari kapısının girdisidir; normal kullanıcı yazamaz.
chown root:root /usr/share/oguzdows/build-info.json
chmod 0644 /usr/share/oguzdows/build-info.json
