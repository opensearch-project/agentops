/**
 * OpenSearch engine mode and optimized-instance-family constants and helpers.
 *
 * "Optimized Engine" in AWS managed OpenSearch is the OPTIMIZED EngineMode,
 * backed by the OR1/OR2/OM2/OI2 instance families. See
 * https://docs.aws.amazon.com/opensearch-service/latest/developerguide/or1.html
 */

export const EngineMode = {
  GENERAL: 'GENERAL',
  OPTIMIZED: 'OPTIMIZED',
};

export const UseCase = {
  SEARCH: 'SEARCH',
  VECTOR: 'VECTOR',
  OBSERVABILITY: 'OBSERVABILITY',
  MIXED: 'MIXED',
};

// Optimized instance families. OR1/OR2/OM2 use gp3/io1 EBS; OI2 uses local NVMe.
export const OPTIMIZED_FAMILIES = ['or1', 'or2', 'om2', 'oi2'];

// OI2 uses local NVMe disks and takes no EBS configuration.
export const NVME_FAMILIES = ['oi2'];

// Optimized Engine domains require OpenSearch 3.5 or later. The developer guide
// still lists 2.11, but CreateDomain rejects < 3.5 with a ValidationException.
export const OPTIMIZED_MIN_VERSION = { major: 3, minor: 5 };

/**
 * The instance family prefix of an OpenSearch instance type, e.g.
 * 'or1.2xlarge.search' -> 'or1', 'r6g.large.search' -> 'r6g'. Returns '' for
 * empty input.
 */
export function instanceFamily(instanceType) {
  if (!instanceType) return '';
  return String(instanceType).split('.')[0].toLowerCase();
}

/** True when the instance type belongs to an optimized family (OR1/OR2/OM2/OI2). */
export function isOptimizedInstanceType(instanceType) {
  return OPTIMIZED_FAMILIES.includes(instanceFamily(instanceType));
}

/** True when the instance type uses local NVMe and takes no EBS configuration (OI2). */
export function isNvmeOnlyInstanceType(instanceType) {
  return NVME_FAMILIES.includes(instanceFamily(instanceType));
}

// Optimized families offered in the interactive picker, with a short description
// and the sizes AWS supports. The user selects a family, then a size. OR1 is
// omitted here in favor of the newer OR2/OM2; free-text --os-instance-type still
// accepts any valid type.
export const OPTIMIZED_FAMILY_CHOICES = [
  { family: 'or2', label: 'OR2 — general-purpose optimized (EBS)', sizes: ['large', 'xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge', '16xlarge'] },
  { family: 'om2', label: 'OM2 — memory-optimized (EBS)', sizes: ['large', 'xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge', '16xlarge'] },
  { family: 'oi2', label: 'OI2 — local NVMe, no EBS', sizes: ['large', 'xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge', '16xlarge', '24xlarge', '32xlarge'] },
];

// Opinionated default for optimized deployments: general-purpose OR2, small size.
export const DEFAULT_OPTIMIZED_INSTANCE_TYPE = 'or2.large.search';

// Default instance type for the general (standard-engine) opt-out path.
export const DEFAULT_GENERAL_INSTANCE_TYPE = 'r6g.large.search';

/** Compose an OpenSearch instance type from a family and size, e.g. ('or2','large') -> 'or2.large.search'. */
export function optimizedInstanceType(family, size) {
  return `${family}.${size}.search`;
}

/**
 * Build the storage and engine-mode fields for CreateDomain from a config.
 * OI2 uses local NVMe and takes no EBSOptions; OR1/OR2/OM2 and standard types
 * keep gp3 EBS. Optimized instances (by flag or type) get EngineMode=OPTIMIZED
 * and UseCase=OBSERVABILITY. Returns an object spread directly into CreateDomain.
 */
export function buildStorageAndEngineOptions(cfg) {
  const options = {};
  if (!isNvmeOnlyInstanceType(cfg.osInstanceType)) {
    options.EBSOptions = {
      EBSEnabled: true,
      VolumeType: 'gp3',
      VolumeSize: cfg.osVolumeSize,
    };
  }
  const optimized = cfg.engineMode === EngineMode.OPTIMIZED || isOptimizedInstanceType(cfg.osInstanceType);
  if (optimized) {
    options.EngineMode = EngineMode.OPTIMIZED;
    options.UseCase = UseCase.OBSERVABILITY;
  }
  return options;
}

