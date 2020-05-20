-- phpMyAdmin SQL Dump
-- version 4.8.3
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Oct 26, 2019 at 10:24 PM
-- Server version: 10.1.36-MariaDB
-- PHP Version: 7.2.11

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `monitoring`
--
CREATE DATABASE IF NOT EXISTS `monitoring` DEFAULT CHARACTER SET latin1 COLLATE latin1_swedish_ci;
USE `monitoring`;

-- --------------------------------------------------------

--
-- Table structure for table `building_events`
--

DROP TABLE IF EXISTS `building_events`;
CREATE TABLE IF NOT EXISTS `building_events` (
  `id` tinyint(4) NOT NULL AUTO_INCREMENT,
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `online_id` tinyint(4) NOT NULL DEFAULT '0' COMMENT 'online event id',
  `status` enum('OK','DELETE','NEW','UPDATE','OLD','TAN-REQ','TANERR') COLLATE latin1_general_cs NOT NULL DEFAULT 'OK',
  `seed` int(11) NOT NULL,
  `weekday` enum('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `start` time NOT NULL,
  `end` time NOT NULL,
  `title` varchar(30) COLLATE latin1_general_cs NOT NULL,
  `repeats` enum('once','weekly','monthly','biweekly') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `nextdate` date DEFAULT NULL,
  `rooms` varchar(5) CHARACTER SET latin1 NOT NULL,
  `targetTemp` tinyint(4) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM AUTO_INCREMENT=104 DEFAULT CHARSET=latin1 COLLATE=latin1_general_cs COMMENT='events for heating control';

--
-- Dumping data for table `building_events`
--

INSERT INTO `building_events` (`id`, `timestamp`, `online_id`, `status`, `seed`, `weekday`, `start`, `end`, `title`, `repeats`, `nextdate`, `rooms`, `targetTemp`) VALUES
(77, '2018-11-04 12:35:03', 2, 'OK', 24386, 'Sunday', '09:45:00', '12:15:00', 'Sunday Morning Service', 'weekly', '2018-11-11', '1,2', 23),
(81, '2018-10-29 07:46:06', 3, 'OK', 24386, 'Saturday', '10:00:00', '11:15:00', 'Mens Meeting', 'monthly', '2018-11-24', '1', 22),
(100, '2018-11-13 21:30:04', 1, 'OK', 24386, 'Tuesday', '19:30:00', '21:15:00', 'Tuesday Night Service', 'weekly', '2018-11-20', '2', 22),
(0, '2018-11-11 21:28:53', 0, 'OK', 24386, 'Thursday', '21:00:00', '23:58:57', 'manual heating control', 'once', '2016-12-31', '2', 22),
(101, '2018-11-11 21:28:29', 6, 'OLD', 24386, 'Monday', '10:00:00', '11:40:00', 'Ladies meeting', 'weekly', '2018-11-12', '2', 22),
(96, '2018-11-19 08:48:26', 4, 'OLD', 24386, 'Monday', '19:30:00', '19:55:00', 'Elders Meeting', 'biweekly', '2018-11-19', '2', 20),
(98, '2018-11-11 21:28:16', 8, 'OK', 24386, 'Sunday', '13:00:00', '15:00:00', 'VIA Youth', 'weekly', '2018-11-18', '2', 22),
(103, '2018-11-14 21:15:05', 7, 'OK', 24386, 'Wednesday', '19:15:00', '21:00:00', 'Abundant Life', 'weekly', '2018-11-21', '2', 22);

-- --------------------------------------------------------

--
-- Table structure for table `building_logbook`
--

DROP TABLE IF EXISTS `building_logbook`;
CREATE TABLE IF NOT EXISTS `building_logbook` (
  `timestamp` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00' ON UPDATE CURRENT_TIMESTAMP,
  `type` char(15) NOT NULL,
  `where` varchar(55) NOT NULL,
  `text` varchar(255) NOT NULL,
  PRIMARY KEY (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `building_power`
--

DROP TABLE IF EXISTS `building_power`;
CREATE TABLE IF NOT EXISTS `building_power` (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `datetime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `power` float NOT NULL,
  `boiler_on` tinyint(1) NOT NULL,
  `heating_on` tinyint(1) NOT NULL,
  PRIMARY KEY (`Id`),
  KEY `power` (`power`),
  KEY `datetime` (`datetime`)
) ENGINE=MyISAM AUTO_INCREMENT=22566193 DEFAULT CHARSET=latin1 COLLATE=latin1_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `building_templog`
--

DROP TABLE IF EXISTS `building_templog`;
CREATE TABLE IF NOT EXISTS `building_templog` (
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `mainroom` decimal(4,1) NOT NULL,
  `auxtemp` decimal(4,2) DEFAULT NULL,
  `frontroom` decimal(4,2) DEFAULT NULL,
  `heating_on` tinyint(1) NOT NULL,
  `power` int(11) NOT NULL,
  `outdoor` decimal(4,2) DEFAULT '0.00',
  `babyroom` decimal(4,2) NOT NULL,
  PRIMARY KEY (`timestamp`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 COLLATE=latin1_general_ci COMMENT='logging of temperatures, power and heating status';

-- --------------------------------------------------------

--
-- Table structure for table `heating_control`
--

DROP TABLE IF EXISTS `heating_control`;
CREATE TABLE IF NOT EXISTS `heating_control` (
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `id` tinyint(4) NOT NULL,
  `seed` int(11) NOT NULL,
  `ipaddr` varchar(15) COLLATE latin1_general_ci NOT NULL,
  `status` enum('OK','UPDATE') COLLATE latin1_general_ci NOT NULL DEFAULT 'UPDATE',
  `heating` enum('AUTO','ON','OFF','HWONLY') COLLATE latin1_general_ci NOT NULL COMMENT 'heating control mode',
  `autoOnBelow` int(11) NOT NULL,
  `autoOffAbove` int(11) NOT NULL,
  `increasePerHour` decimal(10,1) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1 COLLATE=latin1_general_ci COMMENT='settings for heating automation';

-- --------------------------------------------------------

--
-- Table structure for table `heating_logbook`
--

DROP TABLE IF EXISTS `heating_logbook`;
CREATE TABLE IF NOT EXISTS `heating_logbook` (
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `eventID` smallint(4) NOT NULL COMMENT 'event ID (index)',
  `eventStart` time NOT NULL DEFAULT '00:00:00',
  `estimateOn` time NOT NULL DEFAULT '00:00:00' COMMENT 'calculated switch-on time',
  `actualOn` time NOT NULL DEFAULT '00:00:00' COMMENT 'actual switch on time',
  `actualOff` time NOT NULL DEFAULT '00:00:00' COMMENT 'actual switch off time',
  PRIMARY KEY (`timestamp`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8 COMMENT='logging of heating events';

-- --------------------------------------------------------

--
-- Table structure for table `sensors`
--

DROP TABLE IF EXISTS `sensors`;
CREATE TABLE IF NOT EXISTS `sensors` (
  `computertime` int(11) NOT NULL,
  `heatwater` decimal(4,1) NOT NULL,
  `frontroom` decimal(4,1) NOT NULL,
  `mainroom` decimal(4,1) NOT NULL,
  PRIMARY KEY (`computertime`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

-- --------------------------------------------------------

--
-- Table structure for table `settings`
--

DROP TABLE IF EXISTS `settings`;
CREATE TABLE IF NOT EXISTS `settings` (
  `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `created_at` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `updated_at` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `key` char(25) COLLATE utf8_unicode_ci NOT NULL,
  `value` char(155) COLLATE utf8_unicode_ci NOT NULL,
  `note` char(255) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Dumping data for table `settings`
--

INSERT INTO `settings` (`id`, `created_at`, `updated_at`, `key`, `value`, `note`) VALUES
(1, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'heating', 'AUTO', ''),
(2, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'autoOnBelow', '13', ''),
(3, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'autoOffAbove', '21', ''),
(4, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'increasePerHour', '3', ''),
(5, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFHostAddr', '25.120.190.207', ''),
(6, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFHostPort', '4223', ''),
(7, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFheatSwUID', '6D9', ''),
(8, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFmainTempUID', 'bTh', ''),
(9, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFfrontRoomTempUID', '6Jm', ''),
(10, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFauxTempUID', 'bSC', ''),
(11, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFlightUID', '7dw', ''),
(12, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFLCDUID', 'cYL', ''),
(13, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'reload', '0', ''),
(14, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'restart', '0', ''),
(15, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'wol', '0', ''),
(16, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'debug', '0', ''),
(17, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'silent', '1', ''),
(18, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'reboot', '0', ''),
(19, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'interval', '5', ''),
(20, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'homepageAddr', 'ennisevangelicalchurch.org', ''),
(21, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'tempPath', 'c:\\tmp\\', ''),
(22, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'sundayRecording', 'c:\\daten\\sunday.wma', ''),
(24, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'adminEmail', 'matthiku@yahoo.com', ''),
(25, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'backupAdmin', 'church.ennis@gmail.com', ''),
(26, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'youLessURL', 'http://192.168.1.10/a?f=j', ''),
(27, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'TFmotionSwUID', 'iSC', ''),
(28, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'buildingAPIurl', 'http://buildingapi.eec.ie/', ''),
(29, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'buildingAPIclient_secret', 'RYGnyjKP', ''),
(30, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'seed', '12345', ''),
(31, '0000-00-00 00:00:00', '0000-00-00 00:00:00', 'pcMACaddr', '00-19-B9-10-C5-98', '');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
