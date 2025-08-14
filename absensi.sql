/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.5.29-MariaDB, for debian-linux-gnu (aarch64)
--
-- Host: localhost    Database: absensi
-- ------------------------------------------------------
-- Server version	10.5.29-MariaDB-0+deb11u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `data_absen`
--

DROP TABLE IF EXISTS `data_absen`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `data_absen` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `tag` varchar(50) DEFAULT NULL,
  `datetime` datetime DEFAULT NULL,
  `status` tinyint(4) DEFAULT NULL,
  `keterangan` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=143 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `data_absen`
--

LOCK TABLES `data_absen` WRITE;
/*!40000 ALTER TABLE `data_absen` DISABLE KEYS */;
INSERT INTO `data_absen` VALUES (45,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(46,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(47,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(48,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(49,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(50,'564339348685','2025-06-19 10:31:00',2,'Kartu atau mesin tidak terdaftar'),(51,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(52,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(53,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(54,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(55,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(56,'564339348685','2025-06-19 10:31:01',2,'Kartu atau mesin tidak terdaftar'),(57,'564339348685','2025-06-19 10:33:02',2,'Kartu atau mesin tidak terdaftar'),(58,'564339348685','2025-06-19 10:33:32',2,'Kartu atau mesin tidak terdaftar'),(59,'564339348685','2025-06-19 10:33:33',2,'Kartu atau mesin tidak terdaftar'),(60,'564339348685','2025-06-19 10:34:16',2,'Kartu atau mesin tidak terdaftar'),(61,'564339348685','2025-06-19 10:34:19',2,'Kartu atau mesin tidak terdaftar'),(62,'564339348685','2025-06-19 10:34:22',2,'Kartu atau mesin tidak terdaftar'),(63,'564339348685','2025-06-19 10:34:25',2,'Kartu atau mesin tidak terdaftar'),(64,'564339348685','2025-06-19 10:46:17',2,'Kartu atau mesin tidak terdaftar'),(65,'564339348685','2025-06-19 10:46:22',2,'Kartu atau mesin tidak terdaftar'),(66,'564339348685','2025-06-19 10:46:27',2,'Kartu atau mesin tidak terdaftar'),(67,'564339348685','2025-06-19 11:00:39',2,'Kartu atau mesin tidak terdaftar'),(68,'564339348685','2025-06-19 11:25:41',2,'Kartu atau mesin tidak terdaftar'),(69,'564339348685','2025-06-19 11:25:46',2,'Kartu atau mesin tidak terdaftar'),(70,'564339348685','2025-06-19 11:25:53',2,'Kartu atau mesin tidak terdaftar'),(71,'564339348685','2025-06-19 11:51:23',2,'Kartu atau mesin tidak terdaftar'),(72,'564339348685','2025-06-19 11:51:28',2,'Kartu atau mesin tidak terdaftar'),(73,'564339348685','2025-06-19 11:51:29',2,'Kartu atau mesin tidak terdaftar'),(74,'564339348685','2025-06-19 11:54:35',2,'Kartu atau mesin tidak terdaftar'),(75,'564339348685','2025-06-19 11:54:42',2,'Kartu atau mesin tidak terdaftar'),(76,'564339348685','2025-06-19 12:09:48',2,'Kartu atau mesin tidak terdaftar'),(77,'564339348685','2025-06-19 12:09:53',2,'Kartu atau mesin tidak terdaftar'),(78,'564339348685','2025-06-19 12:09:56',2,'Kartu atau mesin tidak terdaftar'),(79,'564339348685','2025-06-19 14:38:21',2,'Kartu atau mesin tidak terdaftar'),(80,'564339348685','2025-06-19 14:38:33',2,'Kartu atau mesin tidak terdaftar'),(81,'564339348685','2025-06-19 14:38:44',2,'Kartu atau mesin tidak terdaftar'),(82,'564339348685','2025-06-19 14:38:52',2,'Kartu atau mesin tidak terdaftar'),(83,'564339348685','2025-06-19 14:54:49',2,'Kartu atau mesin tidak terdaftar'),(84,'564339348685','2025-06-19 14:54:58',2,'Kartu atau mesin tidak terdaftar'),(104,'564339348685','2025-06-19 16:04:49',2,'Kartu atau mesin tidak terdaftar'),(105,'564339348685','2025-06-19 16:04:54',2,'Kartu atau mesin tidak terdaftar'),(106,'837872331242','2025-06-19 16:05:43',2,'Jadwal tidak tersedia'),(107,'837872331242','2025-06-19 16:05:52',2,'Jadwal tidak tersedia'),(108,'837872331242','2025-06-19 16:06:20',2,'Jadwal tidak tersedia'),(109,'837872331242','2025-06-19 16:06:24',2,'Jadwal tidak tersedia'),(110,'837872331242','2025-06-19 16:06:28',2,'Jadwal tidak tersedia'),(111,'837872331242','2025-06-19 16:06:33',2,'Jadwal tidak tersedia'),(112,'837872331242','2025-06-19 16:10:42',2,'Jadwal tidak tersedia'),(113,'837872331242','2025-06-19 16:12:19',2,'Jadwal tidak tersedia'),(114,'837872331242','2025-06-19 16:12:25',2,'Jadwal tidak tersedia'),(115,'837872331242','2025-06-19 16:14:01',2,'Jadwal tidak tersedia'),(116,'837872331242','2025-06-19 16:14:08',2,'Jadwal tidak tersedia'),(117,'837872331242','2025-06-19 16:15:06',2,'Jadwal tidak tersedia'),(118,'837872331242','2025-06-19 16:16:12',2,'Jadwal tidak tersedia'),(119,'837872331242','2025-06-19 16:16:18',2,'Jadwal tidak tersedia'),(120,'837872331242','2025-06-19 16:16:23',2,'Jadwal tidak tersedia'),(121,'837872331242','2025-06-19 16:16:28',2,'Jadwal tidak tersedia'),(122,'837872331242','2025-06-19 16:16:35',2,'Jadwal tidak tersedia'),(123,'837872331242','2025-06-19 16:17:16',2,'Jadwal tidak tersedia'),(124,'837872331242','2025-06-19 16:53:18',2,'Jadwal tidak tersedia'),(125,'837872331242','2025-06-19 16:58:58',2,'Jadwal tidak tersedia'),(126,'564339348685','2025-06-19 16:59:06',2,'Kartu atau mesin tidak terdaftar'),(127,'564339348685','2025-06-19 16:59:11',2,'Kartu atau mesin tidak terdaftar'),(128,'564339348685','2025-06-19 16:59:13',2,'Kartu atau mesin tidak terdaftar'),(129,'564339348685','2025-06-19 16:59:14',2,'Kartu atau mesin tidak terdaftar'),(130,'564339348685','2025-06-19 16:59:15',2,'Kartu atau mesin tidak terdaftar'),(131,'564339348685','2025-06-19 16:59:17',2,'Kartu atau mesin tidak terdaftar'),(132,'564339348685','2025-06-19 16:59:19',2,'Kartu atau mesin tidak terdaftar'),(133,'564339348685','2025-06-19 16:59:20',2,'Kartu atau mesin tidak terdaftar'),(134,'564339348685','2025-06-19 16:59:23',2,'Kartu atau mesin tidak terdaftar'),(135,'837872331242','2025-06-19 16:59:27',2,'Jadwal tidak tersedia'),(136,'837872331242','2025-06-19 16:59:29',2,'Jadwal tidak tersedia'),(137,'837872331242','2025-06-19 16:59:32',2,'Jadwal tidak tersedia'),(138,'837872331242','2025-06-19 16:59:34',2,'Jadwal tidak tersedia'),(139,'837872331242','2025-06-19 16:59:36',2,'Jadwal tidak tersedia'),(140,'837872331242','2025-06-19 17:29:35',0,NULL),(141,'837872331242','2025-06-19 17:30:05',0,NULL),(142,'837872331242','2025-06-19 17:30:09',0,NULL);
/*!40000 ALTER TABLE `data_absen` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-06-19 17:49:32
