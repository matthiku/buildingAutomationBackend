-- initialize the database

-- Create table building_logs
CREATE TABLE `building_logs` (
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `what` char(25) COLLATE utf8_unicode_ci NOT NULL,
  `where` char(55) COLLATE utf8_unicode_ci NOT NULL,
  `text` char(255) COLLATE utf8_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- Create table events
CREATE TABLE `events` (
  `id` int(10) UNSIGNED NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ipaddr` varchar(15) COLLATE utf8_unicode_ci NOT NULL,
  `seed` int(11) NOT NULL,
  `status` enum('OK','DELETE','NEW','UPDATE','OLD','TAN-REQ','TANERR') COLLATE utf8_unicode_ci NOT NULL,
  `weekday` enum('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') COLLATE utf8_unicode_ci NOT NULL,
  `start` time NOT NULL,
  `end` time NOT NULL,
  `title` varchar(30) COLLATE utf8_unicode_ci NOT NULL,
  `repeats` enum('once','weekly','monthly','biweekly') COLLATE utf8_unicode_ci NOT NULL,
  `nextdate` date NOT NULL,
  `rooms` varchar(5) COLLATE utf8_unicode_ci NOT NULL,
  `targetTemp` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- insert sample events into table
INSERT INTO `events` (`id`, `created_at`, `updated_at`, `ipaddr`, `seed`, `status`, `weekday`, `start`, `end`, `title`, `repeats`, `nextdate`, `rooms`, `targetTemp`) VALUES
(0, '2015-07-26 13:35:04', '2016-11-27 13:30:03', 'matthias', 97763, 'OK', 'Sunday', '09:45:00', '12:15:00', 'Sunday Morning Service', 'weekly', '2016-12-04', '1,2', 21);

-- create table settings
CREATE TABLE `settings` (
  `id` int(10) UNSIGNED NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `key` char(25) COLLATE utf8_unicode_ci NOT NULL,
  `value` char(155) COLLATE utf8_unicode_ci NOT NULL,
  `note` char(255) COLLATE utf8_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- insert default settings into table
INSERT INTO `settings` (`id`, `created_at`, `updated_at`, `key`, `value`, `note`) VALUES
(0, CURRENT_TIMESTAMP, '2015-11-26 15:51:40', 'seed', '68130', ''),
(1, CURRENT_TIMESTAMP, '2015-11-26 15:51:40', 'heating', 'AUTO', 'old value: ON'),
(2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'autoOnBelow', '13', ''),
(3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'autoOffAbove', '25', ''),
(4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'increasePerHour', '2.5', ''),
(5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFHostAddr', 'localhost', '25.120.190.207'),
(6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFHostPort', '4223', ''),
(7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFheatSwUID', '6D9', ''),
(8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFmainTempUID', 'bTh', ''),
(9, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFfrontRoomTempUID', '6Jm', ''),
(10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFauxTempUID', 'bSC', ''),
(11, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFlightUID', '7dw', ''),
(12, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFLCDUID', 'cYL', ''),
(13, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'reload', '0', ''),
(14, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'restart', '0', ''),
(15, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'wol', '0', ''),
(16, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'debug', '0', ''),
(17, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'silent', '1', ''),
(18, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'reboot', '0', ''),
(19, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'interval', '5', ''),
(20, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'homepageAddr', 'ennisevangelicalchurch.org', ''),
(21, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'tempPath', 'c:\\tmp\\', ''),
(22, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'sundayRecording', 'c:\\daten\\sunday.wma', ''),
(24, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'adminEmail', 'testuser1@gmail.com', ''),
(25, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'buildingAPIurl', 'http://yourhost.org/buildingAPI/public/', ''),
(26, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'buildingAPIclient_secret', 'RYGnyjKP', ''),
(27, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'youLessURL', 'http://192.168.0.10/a?f=j', ''),
(28, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'backupAdmin', 'testuser2@gmail.com', ''),
(29, CURRENT_TIMESTAMP, '2015-11-26 15:55:00', 'status', 'OK', ''),
(30, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'TFmotionSwUID', 'iSC', ''),
(31, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'pcMACaddr', '00-19-B9-10-C5-98', '');

-- create table temp_logs
CREATE TABLE `temp_logs` (
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `mainroom` decimal(3,1) NOT NULL,
  `auxtemp` decimal(3,1) NOT NULL,
  `frontroom` decimal(3,1) NOT NULL,
  `heating_on` tinyint(1) NOT NULL,
  `power` int(11) NOT NULL,
  `outdoor` decimal(3,1) NOT NULL,
  `babyroom` decimal(3,1) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- create table power_logs
CREATE TABLE `power_logs` (
	`updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`power` INT(11) NOT NULL,
	`heating_on` TINYINT(1) NOT NULL,
	`boiler_on` TINYINT(1) NOT NULL,
	PRIMARY KEY (`updated_at`)
);


ALTER TABLE `building_logs`
  ADD PRIMARY KEY (`updated_at`);

ALTER TABLE `events`
  ADD PRIMARY KEY (`id`);

ALTER TABLE `settings`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `key` (`key`),
  ADD KEY `key_2` (`key`);

ALTER TABLE `temp_logs`
  ADD PRIMARY KEY (`updated_at`),
  ADD KEY `updated_at` (`updated_at`);
