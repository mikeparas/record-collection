import { Module } from '@nestjs/common';
import { ArtistsController } from './controllers/artists.controller';
import ArtistsService from './services/artists.service';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Artist } from './entities/artist.entity';
import { ArtistExtra } from './entities/artist-extra.entity';
import { DiscogsModule } from '../shared/discogs/discogs.module';

@Module({
  controllers: [ArtistsController],
  providers: [ArtistsService],
  imports: [TypeOrmModule.forFeature([Artist, ArtistExtra]), DiscogsModule],
})
export default class ArtistsModule {}
