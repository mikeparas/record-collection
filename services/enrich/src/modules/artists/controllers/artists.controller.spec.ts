import { Test, TestingModule } from '@nestjs/testing';
import { randomUUID } from 'node:crypto';
import { Artist } from '../entities/artist.entity';
import { ArtistsService } from '../services/artists.service';
import { ArtistsController } from './artists.controller';

describe('ArtistsController', () => {
  let controller: ArtistsController;
  let service: ArtistsService;

  beforeAll(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [ArtistsController],
      providers: [
        {
          provide: ArtistsService,
          useValue: {
            getArtist: jest.fn(),
            enrich: jest.fn(),
          },
        },
      ],
    }).compile();

    controller = module.get<ArtistsController>(ArtistsController);
    service = module.get<ArtistsService>(ArtistsService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('handleCreated', () => {
    test('should populate information from external sources', async () => {
      expect.assertions(4);

      const artistId = randomUUID();
      const message = { artistId };

      const mockArtist = new Artist({
        id: artistId,
        name: 'New Artist',
        sortName: 'newartist',
        integrations: {
          discogs: 1234567,
        },
      });

      const mockGetArtist = jest
        .spyOn(service, 'getArtist')
        .mockResolvedValue(mockArtist);
      const mockEnrich = jest.spyOn(service, 'enrich');

      await controller.handleCreated(message);

      expect(mockGetArtist).toHaveBeenCalledTimes(1);
      expect(mockGetArtist).toHaveBeenCalledWith(artistId);

      expect(mockEnrich).toHaveBeenCalledTimes(1);
      expect(mockEnrich).toHaveBeenCalledWith(mockArtist);
    });

    test('should populate information from external sources', async () => {
      expect.assertions(3);

      const artistId = randomUUID();
      const message = { artistId };

      const mockArtist = null;

      const mockGetArtist = jest
        .spyOn(service, 'getArtist')
        .mockResolvedValue(mockArtist);
      const mockEnrich = jest.spyOn(service, 'enrich');

      await controller.handleCreated(message);

      expect(mockGetArtist).toHaveBeenCalledTimes(1);
      expect(mockGetArtist).toHaveBeenCalledWith(artistId);

      expect(mockEnrich).not.toHaveBeenCalled();
    });
  });
});
