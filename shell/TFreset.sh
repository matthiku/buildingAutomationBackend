/etc/init.d/brickd restart

tinkerforge call master-brick 6k2KqL reset

tinkerforge call master-brick 6k2KqL reset

tinkerforge call temperature-bricklet bSC set-i2c-mode 1
tinkerforge call temperature-bricklet bTh set-i2c-mode 1
tinkerforge call temperature-bricklet 6Jm set-i2c-mode 1


tinkerforge enumerate | grep 'uid'
