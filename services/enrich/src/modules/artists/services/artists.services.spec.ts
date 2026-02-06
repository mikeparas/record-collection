import { Repository } from 'typeorm';
import ArtistsService from './artists.service';
import { Artist } from '../entities/artist.entity';
import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { randomUUID } from 'crypto';
import { ArtistExtra } from '../entities/artist-extra.entity';
import { DiscogsService } from '../../shared/discogs/services/discogs.service';

describe('ArtistsService', () => {
  let service: ArtistsService;
  let discogs: DiscogsService;
  let artistRepo: Repository<Artist>;
  let artistExtraRepo: Repository<ArtistExtra>;

  beforeAll(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ArtistsService,
        {
          provide: getRepositoryToken(Artist),
          useValue: {
            findOneBy: jest.fn(),
          },
        },
        {
          provide: getRepositoryToken(ArtistExtra),
          useValue: {
            findOneBy: jest.fn(),
            save: jest.fn(),
          },
        },
        {
          provide: DiscogsService,
          useValue: {
            enrichArtist: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<ArtistsService>(ArtistsService);
    discogs = module.get<DiscogsService>(DiscogsService);
    artistRepo = module.get<Repository<Artist>>(getRepositoryToken(Artist));
    artistExtraRepo = module.get<Repository<ArtistExtra>>(
      getRepositoryToken(ArtistExtra),
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getArtist', () => {
    test('should get an Artist by id', async () => {
      expect.assertions(3);

      const artistId = randomUUID();

      const mockArtist = new Artist({
        id: artistId,
        name: 'Gorilla Biscuits',
        sortName: 'gorillabiscuits',
        integrations: {
          discogs: 12344321,
        },
      });

      const mockFind = jest
        .spyOn(artistRepo, 'findOneBy')
        .mockResolvedValue(mockArtist);

      const artist = await service.getArtist(artistId);
      expect(artist).toMatchObject(mockArtist);

      expect(mockFind).toHaveBeenCalledTimes(1);
      expect(mockFind).toHaveBeenCalledWith({ id: artistId });
    });
  });

  describe('enrich', () => {
    test('should populate external data for configured integrations', async () => {
      // tests one integration

      expect.assertions(7);

      const discogsId = 12341234;

      const mockArtist = new Artist({
        id: randomUUID(),
        name: 'Minor Threat',
        sortName: 'minorthreat',
        integrations: {
          discogs: discogsId,
        },
      });

      const mockDiscogsArtist = {
        name: 'Minor Threat',
        id: discogsId,
        url: 'https://discogs.com',
        images: ['https://discogs.com/example.jpg'],
      };

      const expectedArtistExtra = {
        id: mockArtist.id,
        data: {
          discogs: mockDiscogsArtist,
        },
      };

      const mockFind = jest
        .spyOn(artistExtraRepo, 'findOneBy')
        .mockResolvedValue(null);
      const mockDiscogsGetArtist = jest
        .spyOn(discogs, 'enrichArtist')
        .mockResolvedValue(mockDiscogsArtist);
      const mockSave = jest.spyOn(artistExtraRepo, 'save').mockResolvedValue({
        ...expectedArtistExtra,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      const artistExtra = await service.enrich(mockArtist);
      expect(artistExtra).toMatchObject(expectedArtistExtra);

      expect(mockFind).toHaveBeenCalledTimes(1);
      expect(mockFind).toHaveBeenCalledWith({ id: mockArtist.id });

      expect(mockDiscogsGetArtist).toHaveBeenCalledTimes(1);
      expect(mockDiscogsGetArtist).toHaveBeenCalledWith(discogsId);

      expect(mockSave).toHaveBeenCalledTimes(1);
      expect(mockSave).toHaveBeenCalledWith(expectedArtistExtra);
    });

    test('should not populate external data for no configured integrations', async () => {
      // tests no integrations

      expect.assertions(6);

      const mockArtist = new Artist({
        id: randomUUID(),
        name: 'Minor Threat',
        sortName: 'minorthreat',
        integrations: {}, // no integrations here
      });

      const expectedArtistExtra = {
        id: mockArtist.id,
        data: {},
      };

      const mockFind = jest
        .spyOn(artistExtraRepo, 'findOneBy')
        .mockResolvedValue(null);
      const mockDiscogsGetArtist = jest.spyOn(discogs, 'enrichArtist');
      const mockSave = jest.spyOn(artistExtraRepo, 'save').mockResolvedValue({
        ...expectedArtistExtra,
        createdAt: new Date(),
        updatedAt: new Date(),
      });

      const artistExtra = await service.enrich(mockArtist);
      expect(artistExtra).toMatchObject(expectedArtistExtra);

      expect(mockFind).toHaveBeenCalledTimes(1);
      expect(mockFind).toHaveBeenCalledWith({ id: mockArtist.id });

      expect(mockDiscogsGetArtist).not.toHaveBeenCalled();

      expect(mockSave).toHaveBeenCalledTimes(1);
      expect(mockSave).toHaveBeenCalledWith(expectedArtistExtra);
    });
  });
});
