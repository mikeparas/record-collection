import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { AsyncMicroserviceOptions, Transport } from '@nestjs/microservices';
import { ConfigService } from '@nestjs/config';
import { RMQTypeDeserializer } from './common/microservices/deserializers/rmq-type.deserializer';

const buildRmqUrl = (configService: ConfigService) => {
  const rmq_user = configService.get<string>('MQ_USER') ?? 'guest';
  const rmq_password = encodeURIComponent(
    configService.get<string>('MQ_PASSWORD') ?? 'guest',
  );
  const rmq_host = configService.get<string>('MQ_HOST') ?? 'localhost';
  const rmq_port = configService.get<string>('MQ_PORT') ?? '5672';

  const rmq_url = `amqp://${rmq_user}:${rmq_password}@${rmq_host}:${rmq_port}/`;
  return rmq_url;
};

async function bootstrap() {
  const app = await NestFactory.createMicroservice<AsyncMicroserviceOptions>(
    AppModule,
    {
      useFactory: (configService: ConfigService) => ({
        transport: Transport.RMQ,
        options: {
          urls: [buildRmqUrl(configService)],
          queue: configService.get<string>('MQ_QUEUE_EXTERNAL_DATA'),
          deserializer: new RMQTypeDeserializer(),
        },
      }),
      inject: [ConfigService],
    },
  );

  await app.listen();
}
void bootstrap();
