package dev.campushubbackend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class CampusHubBackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(CampusHubBackendApplication.class, args);
	}

}
