import { INestMicroservice } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import { Transport } from '@nestjs/microservices';
import { AppModule } from '../../src/app.module';
import { Artist } from '../../src/modules/artists/entities/artist.entity';
import { Repository } from 'typeorm';
import { ArtistExtra } from '../../src/modules/artists/entities/artist-extra.entity';
import { getRepositoryToken } from '@nestjs/typeorm';
import RMQClient from '../utils/rmq.client';
import { randomUUID } from 'crypto';
import * as nock from 'nock';

import * as discogsArtist from '../fixtures/discogs/artist.json';
import { DiscogsArtist } from '../../src/modules/shared/discogs/schemas/artist.schema';
import { setTimeout } from 'timers/promises';
import { RMQTypeDeserializer } from '../../src/common/microservices/deserializers/rmq-type.deserializer';

const rmq_user = process.env.MQ_USER ?? 'guest';
const rmq_pass_encoded = encodeURIComponent(process.env.MQ_PASS ?? 'guest');
const rmq_host = process.env.MQ_HOST ?? 'localhost';
const rmq_port = process.env.MQ_PORT ?? '5672';

describe('Integration Tests - Artists', () => {
  let app: INestMicroservice;
  //   let app: INestApplication;
  const amqpUrl = `amqp://${rmq_user}:${rmq_pass_encoded}@${rmq_host}:${rmq_port}/`;
  const exchange = `test-${process.env.MQ_EXCHANGE ?? 'record_collection'}`;
  const queue = `test-${process.env.MQ_QUEUE ?? 'external_data_v1'}`;
  let moduleFixture: TestingModule;
  let artistRepo: Repository<Artist>;
  let artistExtraRepo: Repository<ArtistExtra>;
  let rmqClient: RMQClient;

  const pollArtistExtra = async (
    op: () => Promise<ArtistExtra | null>,
    attempt: number,
  ): Promise<ArtistExtra | null> => {
    if (attempt < 10) {
      await setTimeout(500);
      const result = await op();
      if (result !== null) {
        return result;
      }
      return await pollArtistExtra(op, attempt + 1);
    }
    return null;
  };

  beforeAll(async () => {
    nock('https://api.discogs.com')
      .get('/artists/9806635')
      .reply(200, discogsArtist);

    rmqClient = new RMQClient(amqpUrl, exchange, queue);
    await rmqClient.connect();

    moduleFixture = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestMicroservice({
      transport: Transport.RMQ,
      options: {
        urls: [amqpUrl],
        queue,
        queueOptions: {
          // should match RMQClient
          durable: false,
          autoDelete: true,
          exclusive: false,
        },
        deserializer: new RMQTypeDeserializer(),
      },
    });

    await app.listen();

    artistRepo = moduleFixture.get<Repository<Artist>>(
      getRepositoryToken(Artist),
    );
    artistExtraRepo = moduleFixture.get<Repository<ArtistExtra>>(
      getRepositoryToken(ArtistExtra),
    );
  });

  afterAll(async () => {
    await rmqClient.close();
    await app.close();
  });

  describe('artists.created message', () => {
    test('should populate information from external sources', async () => {
      expect.assertions(2);
      const artistId = randomUUID();

      const artist = artistRepo.create({
        id: artistId,
        name: 'Doomsday',
        sortName: 'doomsday',
        integrations: {
          discogs: 9806635,
        },
      });
      await artistRepo.save(artist);

      rmqClient.publishMessage({ artistId }, 'artist.created');

      const artistExtra = await pollArtistExtra(
        () => artistExtraRepo.findOneBy({ id: artistId }),
        1,
      );

      expect(artistExtra).not.toBeNull();
      expect(artistExtra!.data).toMatchObject({
        discogs: {
          id: discogsArtist.id,
          name: discogsArtist.name,
          url: discogsArtist.uri,
          images: [discogsArtist.images[0].uri],
        } as DiscogsArtist,
      });
    });
  });
});
