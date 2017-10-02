-- initialize the local database

-- Create table building_logs
CREATE TABLE IF NOT EXISTS `building_logs` (
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `what` char(25) COLLATE utf8_unicode_ci NOT NULL,
  `where` char(55) COLLATE utf8_unicode_ci NOT NULL,
  `text` char(255) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- create table temp_logs
CREATE TABLE IF NOT EXISTS `temp_logs` (
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `mainroom` decimal(3,1) NOT NULL,
  `auxtemp` decimal(3,1) NOT NULL,
  `frontroom` decimal(3,1) NOT NULL,
  `heating_on` tinyint(1) NOT NULL,
  `power` int(11) NOT NULL,
  `outdoor` decimal(3,1) NOT NULL,
  `babyroom` decimal(3,1) NOT NULL,
  PRIMARY KEY (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- create table power_logs
CREATE TABLE IF NOT EXISTS `power_logs` (
	`updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`power` INT(11) NOT NULL,
	`heating_on` TINYINT(1) NOT NULL,
	`boiler_on` TINYINT(1) NOT NULL,
	PRIMARY KEY (`updated_at`)
);

-- create table building_power
CREATE TABLE IF NOT EXISTS `building_power` (
	`datetime` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`power` CHAR(5) NOT NULL,
	`boiler_on` CHAR(1) NOT NULL,
	`heating_on` CHAR(1) NOT NULL
) ENGINE=InnoDB;


-- Create table events
CREATE TABLE IF NOT EXISTS `events` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`ipaddr` VARCHAR(15) NOT NULL COLLATE 'utf8_unicode_ci',
	`seed` INT(11) NOT NULL,
	`status` ENUM('OK','DELETE','NEW','UPDATE','OLD','TAN-REQ','TANERR') NOT NULL COLLATE 'utf8_unicode_ci',
	`weekday` ENUM('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') NOT NULL COLLATE 'utf8_unicode_ci',
	`start` TIME NOT NULL,
	`end` TIME NOT NULL,
	`title` VARCHAR(30) NOT NULL COLLATE 'utf8_unicode_ci',
	`repeats` ENUM('once','weekly','monthly','biweekly') NOT NULL COLLATE 'utf8_unicode_ci',
	`nextdate` DATE NOT NULL,
	`rooms` VARCHAR(5) NOT NULL COLLATE 'utf8_unicode_ci',
	`targetTemp` INT(11) NOT NULL,
	PRIMARY KEY (`id`)
) COLLATE='utf8_unicode_ci' ENGINE=InnoDB;

-- insert sample events into table
INSERT INTO `events` (`ipaddr`, `seed`, `status`, `weekday`, `start`, `end`, `title`, `repeats`, `nextdate`, `rooms`, `targetTemp`) VALUES
('some_ip', 97763, 'OK', 'Sunday', '09:45:00', '12:15:00', 'Sunday Morning Service', 'weekly', '2016-12-04', '1,2', 21);

-- create table settings
CREATE TABLE IF NOT EXISTS `settings` (
  `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `key` char(25) COLLATE utf8_unicode_ci NOT NULL,
  `value` char(155) COLLATE utf8_unicode_ci NOT NULL,
  `note` char(255) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- insert default settings into table
INSERT INTO `settings` (`key`, `value`, `note`) VALUES
  ('seed', '68130', ''),
  ('heating', 'AUTO', 'old value: ON'),
  ('autoOnBelow', '13', ''),
  ('autoOffAbove', '25', ''),
  ('increasePerHour', '2.5', ''),
  ('TFHostAddr', 'localhost', '25.120.190.207'),
  ('TFHostPort', '4223', ''),
  ('TFheatSwUID', '6D9', ''),
  ('TFmainTempUID', 'bTh', ''),
  ('TFfrontRoomTempUID', '6Jm', ''),
  ('TFauxTempUID', 'bSC', ''),
  ('TFlightUID', '7dw', ''),
  ('TFLCDUID', 'cYL', ''),
  ('reload', '0', ''),
  ('restart', '0', ''),
  ('wol', '0', ''),
  ('debug', '0', ''),
  ('silent', '1', ''),
  ('reboot', '0', ''),
  ('interval', '5', ''),
  ('homepageAddr', 'ennisevangelicalchurch.org', ''),
  ('tempPath', 'c:\\tmp\\', ''),
  ('sundayRecording', 'c:\\daten\\sunday.wma', ''),
  ('adminEmail', 'testuser1@gmail.com', ''),
  ('buildingAPIurl', 'http://yourhost.org/buildingAPI/public/', ''),
  ('buildingAPIclient_secret', 'RYGnyjKP', ''),
  ('youLessURL', 'http://192.168.0.10/a?f=j', ''),
  ('backupAdmin', 'testuser2@gmail.com', ''),
  ('status', 'OK', ''),
  ('TFmotionSwUID', 'iSC', ''),
  ('pcMACaddr', '00-19-B9-10-C5-98', '');
