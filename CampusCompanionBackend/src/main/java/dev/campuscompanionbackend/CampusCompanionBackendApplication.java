package dev.campuscompanionbackend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class CampusCompanionBackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(CampusCompanionBackendApplication.class, args);
	}

}
