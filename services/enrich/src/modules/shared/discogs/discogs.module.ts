import { Module } from '@nestjs/common';
import { DiscogsService } from './services/discogs.service';
import { HttpModule } from '@nestjs/axios';

@Module({
  imports: [HttpModule],
  providers: [DiscogsService],
  exports: [DiscogsService],
})
export class DiscogsModule {}
