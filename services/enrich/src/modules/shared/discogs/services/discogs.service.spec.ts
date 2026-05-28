import { HttpService } from '@nestjs/axios';
import { DiscogsService } from './discogs.service';
import { DiscogsError } from '../exceptions/exceptions';
import { Test, TestingModule } from '@nestjs/testing';
import { of } from 'rxjs';
import { ConfigService } from '@nestjs/config';

const mockDiscogsToken = 'test-token';
const mockDiscogsUserAgent = 'TestingUserAgent/1.0 (example@example.org)';

describe('DiscogsService', () => {
  let discogs: DiscogsService;
  let http: HttpService;

  const assertDiscogsGetArtist = (
    mockGet: jest.SpyInstance,
    resource: string,
  ) => {
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith(resource, {
      headers: {
        'User-Agent': mockDiscogsUserAgent,
        Authorization: `Discogs token=${mockDiscogsToken}`,
      },
    });
  };

  beforeAll(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DiscogsService,
        {
          provide: HttpService,
          useValue: {
            get: jest.fn(),
          },
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string) => {
              switch (key) {
                case 'DISCOGS_TOKEN':
                  return mockDiscogsToken;
                case 'DISCOGS_USER_AGENT':
                  return mockDiscogsUserAgent;
                default:
                  return null;
              }
            }),
          },
        },
      ],
    }).compile();

    discogs = module.get<DiscogsService>(DiscogsService);
    http = module.get<HttpService>(HttpService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('enrichArtist', () => {
    test('should get artist info from Discogs API', async () => {
      expect.assertions(3);

      const id = 280953;

      const artistResponse = {
        name: 'Ringworm',
        id,
        uri: 'https://www.discogs.com/artist/280953-Ringworm',
        images: [
          {
            type: 'primary',
            uri: 'https://i.discogs.com/_Pl5eJxwohrU-ymSsmBGiV4t4NEVY3spgEgPvZYiZ6U/rs:fit/g:sm/q:90/h:233/w:350/czM6Ly9kaXNjb2dz/LWRhdGFiYXNlLWlt/YWdlcy9BLTI4MDk1/My0xMzY3Nzk3NDY0/LTI3MDEuanBlZw.jpeg',
          },
        ],
      };

      const mockGet = jest.spyOn(http, 'get');
      mockGet.mockReturnValue(
        of({
          status: 200,
          data: artistResponse,
        } as any),
      );

      const data = await discogs.enrichArtist(id);
      expect(data).toMatchObject({
        id,
        name: artistResponse.name,
        url: artistResponse.uri,
        images: [artistResponse.images[0].uri],
      });

      assertDiscogsGetArtist(mockGet, `https://api.discogs.com/artists/${id}`);
    });

    test('should return null if the artist is not found', async () => {
      expect.assertions(3);

      const id = 404;

      const mockGet = jest
        .spyOn(http, 'get')
        .mockReturnValue(of({ status: 404 } as any));

      const data = await discogs.enrichArtist(id);
      expect(data).toBeNull();

      assertDiscogsGetArtist(mockGet, `https://api.discogs.com/artists/${id}`);
    });

    test('should return throw an exception for any other HTTP error status', async () => {
      expect.assertions(3);

      const id = 500;

      const mockGet = jest
        .spyOn(http, 'get')
        .mockReturnValue(of({ status: 500 } as any));

      await expect(discogs.enrichArtist(id)).rejects.toThrow(DiscogsError);

      assertDiscogsGetArtist(mockGet, `https://api.discogs.com/artists/${id}`);
    });
  });
});
