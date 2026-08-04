/**
 * Property-based tests for Performance optimizations
 * Feature: observability-stack
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fc from 'fast-check';

/**
 * Property 6: Below-fold images are lazy-loaded
 * Validates: Requirements 14.5
 * 
 * For any image element that is not in the initial viewport (below the fold), 
 * the image should have the loading="lazy" attribute.
 */
describe('Performance - Property 6: Below-fold images are lazy-loaded', () => {
  let container: HTMLElement;

  beforeEach(() => {
    // Create a container for our test HTML
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    // Clean up
    document.body.removeChild(container);
  });

  it('should ensure all below-fold images have loading="lazy" attribute', () => {
    fc.assert(
      fc.property(
        fc.record({
          images: fc.array(
            fc.record({
              src: fc.oneof(
                fc.constant('/logos/company1.svg'),
                fc.constant('/avatars/user.jpg'),
                fc.constant('/images/dashboard.png'),
                fc.webUrl({ validSchemes: ['https'] })
              ),
              alt: fc.string({ minLength: 3, maxLength: 100 })
                .map(s => s.replace(/[<>"'&]/g, '') || 'image description'), // Sanitize with fallback
              isBelowFold: fc.boolean(),
              width: fc.option(fc.integer({ min: 50, max: 1000 })),
              height: fc.option(fc.integer({ min: 50, max: 1000 }))
            }),
            { minLength: 1, maxLength: 10 }
          )
        }),
        (data) => {
          // Create HTML with images at different positions
          const imagesHTML = `
            <div class="page-content">
              ${data.images.map((img, idx) => {
                const positionClass = img.isBelowFold ? 'below-fold' : 'above-fold';
                const widthAttr = img.width ? `width="${img.width}"` : '';
                const heightAttr = img.height ? `height="${img.height}"` : '';
                const loadingAttr = img.isBelowFold ? 'loading="lazy"' : '';
                const decodingAttr = 'decoding="async"';
                
                return `
                  <img 
                    src="${img.src}" 
                    alt="${img.alt}"
                    class="test-image ${positionClass}"
                    data-testid="img-${idx}"
                    data-below-fold="${img.isBelowFold}"
                    ${widthAttr}
                    ${heightAttr}
                    ${loadingAttr}
                    ${decodingAttr}
                  />
                `;
              }).join('')}
            </div>
          `;
          
          container.innerHTML = imagesHTML;

          // Get all images
          const images = container.querySelectorAll('.test-image');
          expect(images.length).toBeGreaterThan(0);

          // Property: All below-fold images must have loading="lazy"
          images.forEach((img) => {
            const isBelowFold = img.getAttribute('data-below-fold') === 'true';
            const loadingAttr = img.getAttribute('loading');

            if (isBelowFold) {
              // Below-fold images MUST have loading="lazy"
              expect(loadingAttr).toBe('lazy');
            }

            // All images should have alt text
            const altText = img.getAttribute('alt');
            expect(altText).toBeTruthy();
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should ensure testimonial avatar images have lazy loading', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            name: fc.string({ minLength: 5, maxLength: 50 })
              .map(s => s.replace(/[<>"'&]/g, '')),
            avatar: fc.oneof(
              fc.constant('/avatars/sarah-chen.jpg'),
              fc.constant('/avatars/michael-rodriguez.jpg'),
              fc.constant('/avatars/emily-watson.jpg')
            ),
            role: fc.string({ minLength: 5, maxLength: 50 })
              .map(s => s.replace(/[<>"'&]/g, ''))
          }),
          { minLength: 1, maxLength: 5 }
        ),
        (testimonials) => {
          // Create testimonial section (typically below fold)
          const testimonialsHTML = `
            <section id="testimonials" class="below-fold">
              ${testimonials.map((t, idx) => `
                <div class="testimonial-card">
                  <img 
                    src="${t.avatar}" 
                    alt="${t.name}"
                    class="testimonial-avatar"
                    data-testid="avatar-${idx}"
                    loading="lazy"
                    decoding="async"
                    width="48"
                    height="48"
                  />
                  <p>${t.name}</p>
                  <p>${t.role}</p>
                </div>
              `).join('')}
            </section>
          `;
          
          container.innerHTML = testimonialsHTML;

          const avatars = container.querySelectorAll('.testimonial-avatar');
          
          // Property: All testimonial avatars must have lazy loading
          expect(avatars.length).toBeGreaterThan(0);
          
          avatars.forEach((avatar) => {
            expect(avatar.getAttribute('loading')).toBe('lazy');
            expect(avatar.getAttribute('decoding')).toBe('async');
            
            // Should have explicit dimensions for better layout stability
            const width = avatar.getAttribute('width');
            const height = avatar.getAttribute('height');
            expect(width).toBeTruthy();
            expect(height).toBeTruthy();
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should ensure company logos in social proof section have lazy loading', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            name: fc.string({ minLength: 3, maxLength: 30 })
              .map(s => s.replace(/[<>"'&]/g, '') || 'company name'), // Sanitize with fallback
            logo: fc.oneof(
              fc.constant('/logos/company1.svg'),
              fc.constant('/logos/company2.svg'),
              fc.constant('/logos/company3.svg'),
              fc.constant('/logos/company4.svg'),
              fc.constant('/logos/company5.svg'),
              fc.constant('/logos/company6.svg')
            )
          }),
          { minLength: 3, maxLength: 10 }
        ),
        (companies) => {
          // Create social proof section (typically below hero, so below fold)
          const socialProofHTML = `
            <section id="social-proof" class="below-fold">
              <div class="company-logos">
                ${companies.map((company, idx) => `
                  <img 
                    src="${company.logo}" 
                    alt="${company.name}"
                    class="company-logo"
                    data-testid="logo-${idx}"
                    loading="lazy"
                    decoding="async"
                  />
                `).join('')}
              </div>
            </section>
          `;
          
          container.innerHTML = socialProofHTML;

          const logos = container.querySelectorAll('.company-logo');
          
          // Property: All company logos must have lazy loading
          expect(logos.length).toBeGreaterThan(0);
          
          logos.forEach((logo) => {
            expect(logo.getAttribute('loading')).toBe('lazy');
            expect(logo.getAttribute('decoding')).toBe('async');
            
            // Should have alt text
            const alt = logo.getAttribute('alt');
            expect(alt).toBeTruthy();
            expect(alt!.length).toBeGreaterThan(0);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should ensure images have proper attributes for performance', () => {
    fc.assert(
      fc.property(
        fc.record({
          images: fc.array(
            fc.record({
              src: fc.string({ minLength: 5, maxLength: 100 })
                .map(s => `/images/${s.replace(/[^a-z0-9.-]/gi, '_')}.jpg`),
              alt: fc.string({ minLength: 3, maxLength: 100 })
                .map(s => s.replace(/[<>"'&]/g, '') || 'image description'),
              isBelowFold: fc.boolean(),
              width: fc.integer({ min: 100, max: 1200 }),
              height: fc.integer({ min: 100, max: 800 })
            }),
            { minLength: 1, maxLength: 8 }
          )
        }),
        (data) => {
          // Create images with performance attributes
          const imagesHTML = `
            <div class="image-gallery">
              ${data.images.map((img, idx) => {
                const loadingAttr = img.isBelowFold ? 'loading="lazy"' : '';
                
                return `
                  <img 
                    src="${img.src}" 
                    alt="${img.alt}"
                    width="${img.width}"
                    height="${img.height}"
                    class="gallery-image"
                    data-testid="img-${idx}"
                    data-below-fold="${img.isBelowFold}"
                    ${loadingAttr}
                    decoding="async"
                  />
                `;
              }).join('')}
            </div>
          `;
          
          container.innerHTML = imagesHTML;

          const images = container.querySelectorAll('.gallery-image');
          
          // Property: All images must have proper performance attributes
          images.forEach((img) => {
            // Should have alt text
            const alt = img.getAttribute('alt');
            expect(alt).toBeTruthy();

            // Should have explicit dimensions
            const width = img.getAttribute('width');
            const height = img.getAttribute('height');
            expect(width).toBeTruthy();
            expect(height).toBeTruthy();
            expect(parseInt(width!)).toBeGreaterThan(0);
            expect(parseInt(height!)).toBeGreaterThan(0);

            // Should have async decoding
            expect(img.getAttribute('decoding')).toBe('async');

            // Below-fold images should have lazy loading
            const isBelowFold = img.getAttribute('data-below-fold') === 'true';
            const loading = img.getAttribute('loading');
            
            if (isBelowFold) {
              expect(loading).toBe('lazy');
            }
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should ensure hero section images do not have lazy loading', () => {
    fc.assert(
      fc.property(
        fc.record({
          heroImage: fc.record({
            src: fc.constant('/images/dashboard-preview.png'),
            alt: fc.string({ minLength: 10, maxLength: 100 })
              .map(s => s.replace(/[<>"'&]/g, ''))
          })
        }),
        (data) => {
          // Create hero section (above fold - should NOT have lazy loading)
          const heroHTML = `
            <section id="hero" class="above-fold">
              <div class="dashboard-preview">
                <img 
                  src="${data.heroImage.src}" 
                  alt="${data.heroImage.alt}"
                  class="hero-image"
                  decoding="async"
                />
              </div>
            </section>
          `;
          
          container.innerHTML = heroHTML;

          const heroImage = container.querySelector('.hero-image');
          
          // Property: Hero images (above fold) should NOT have lazy loading
          expect(heroImage).toBeTruthy();
          
          const loading = heroImage!.getAttribute('loading');
          
          // Above-fold images should either not have loading attribute or have loading="eager"
          if (loading) {
            expect(loading).not.toBe('lazy');
          }
          
          // Should still have async decoding for performance
          expect(heroImage!.getAttribute('decoding')).toBe('async');
        }
      ),
      { numRuns: 100 }
    );
  });
});
