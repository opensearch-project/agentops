import { InvalidArgumentError } from 'commander';

export function addProfileOption(program) {
  return program.option('--profile <name>', 'AWS shared configuration profile', (value) => {
    if (!value.trim()) throw new InvalidArgumentError('Profile name must not be empty.');
    return value;
  });
}

/** Select once, before creating SDK clients or SigV4 credential providers. */
export function configureAwsProfile(profile) {
  if (profile !== undefined) process.env.AWS_PROFILE = profile;
}
