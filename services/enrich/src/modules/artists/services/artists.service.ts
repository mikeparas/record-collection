import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Artist } from '../entities/artist.entity';
import { ArtistExtra } from '../entities/artist-extra.entity';
import { DiscogsService } from '../../shared/discogs/services/discogs.service';

@Injectable()
export class ArtistsService {
  constructor(
    @InjectRepository(Artist)
    private readonly artistRepository: Repository<Artist>,
    @InjectRepository(ArtistExtra)
    private readonly artistExtraRepository: Repository<ArtistExtra>,
    private readonly discogsService: DiscogsService,
  ) {}

  async getArtist(id: string): Promise<Artist | null> {
    return this.artistRepository.findOneBy({ id });
  }

  async enrich(artist: Artist): Promise<ArtistExtra> {
    let artistExtra = await this.artistExtraRepository.findOneBy({
      id: artist.id,
    });

    if (!artistExtra) {
      artistExtra = new ArtistExtra(artist.id, {});
      artistExtra.id = artist.id;
    }

    if (artist.integrations.discogs) {
      const discogsArtist = await this.discogsService.enrichArtist(
        artist.integrations.discogs,
      );

      artistExtra.data = {
        ...artistExtra.data,
        discogs: discogsArtist || undefined,
      };
    }

    return this.artistExtraRepository.save(artistExtra);
  }
}

export default ArtistsService;
