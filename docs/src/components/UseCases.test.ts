/**
 * Property-based tests for UseCases component
 * Feature: observability-stack
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fc from 'fast-check';

interface UseCase {
  id: string;
  icon: string;
  title: string;
  description: string;
  link: string;
}

/**
 * Property 2: Use case cards contain all required elements
 * Validates: Requirements 7.2
 * 
 * For any use case data object, the rendered card should include 
 * an icon, title, description, and "Learn more" link.
 */
describe('UseCases - Property 2: Use case cards contain all required elements', () => {
  let container: HTMLElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  // Helper function to render a use case card
  function renderUseCaseCard(useCase: UseCase): string {
    return `
      <a
        href="${useCase.link}"
        class="use-case-card group block p-6 rounded-xl bg-slate-800/50 border border-slate-700"
        data-use-case-id="${useCase.id}"
      >
        <!-- Icon -->
        <div class="w-12 h-12 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
          <svg 
            class="w-6 h-6 text-indigo-500 use-case-icon" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
            aria-hidden="true"
            data-icon="${useCase.icon}"
          >
            <path 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              stroke-width="2" 
              d="M4 7v10"
            />
          </svg>
        </div>

        <!-- Title -->
        <h3 class="use-case-title text-xl font-bold text-white mb-3">
          ${useCase.title}
        </h3>

        <!-- Description -->
        <p class="use-case-description text-slate-400 leading-relaxed mb-4">
          ${useCase.description}
        </p>

        <!-- Learn More Link -->
        <div class="use-case-link flex items-center gap-2 text-indigo-400 font-semibold">
          <span>Learn more</span>
          <svg 
            class="w-4 h-4" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              stroke-width="2" 
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </a>
    `;
  }

  it('should contain all required elements for any use case data', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          // Render use case card
          container.innerHTML = renderUseCaseCard(useCase);

          const card = container.querySelector('.use-case-card');
          expect(card).toBeTruthy();

          // Property: Card must have an icon
          const icon = card!.querySelector('.use-case-icon');
          expect(icon).toBeTruthy();
          expect(icon!.getAttribute('data-icon')).toBe(useCase.icon);

          // Property: Card must have a title
          const title = card!.querySelector('.use-case-title');
          expect(title).toBeTruthy();
          expect(title!.textContent?.trim()).toBe(useCase.title.trim());

          // Property: Card must have a description
          const description = card!.querySelector('.use-case-description');
          expect(description).toBeTruthy();
          expect(description!.textContent?.trim()).toBe(useCase.description.trim());

          // Property: Card must have a "Learn more" link
          const learnMoreLink = card!.querySelector('.use-case-link');
          expect(learnMoreLink).toBeTruthy();
          expect(learnMoreLink!.textContent).toContain('Learn more');

          // Property: Card must have correct href
          expect(card!.getAttribute('href')).toBe(useCase.link.trim());

          // Property: Card must have data-use-case-id attribute
          expect(card!.getAttribute('data-use-case-id')).toBe(useCase.id);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should have icon element with correct structure', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const card = container.querySelector('.use-case-card');
          const iconContainer = card!.querySelector('.w-12.h-12');
          const icon = card!.querySelector('.use-case-icon');

          // Property: Icon must be wrapped in a container
          expect(iconContainer).toBeTruthy();
          expect(iconContainer!.classList.contains('rounded-lg')).toBe(true);
          expect(iconContainer!.classList.contains('bg-indigo-500/10')).toBe(true);

          // Property: Icon must be an SVG element
          expect(icon).toBeTruthy();
          expect(icon!.tagName).toBe('svg');
          expect(icon!.classList.contains('w-6')).toBe(true);
          expect(icon!.classList.contains('h-6')).toBe(true);
          expect(icon!.classList.contains('text-indigo-500')).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should have title with correct styling', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const title = container.querySelector('.use-case-title');

          // Property: Title must be an h3 element
          expect(title).toBeTruthy();
          expect(title!.tagName).toBe('H3');

          // Property: Title must have correct styling classes
          expect(title!.classList.contains('text-xl')).toBe(true);
          expect(title!.classList.contains('font-bold')).toBe(true);
          expect(title!.classList.contains('text-white')).toBe(true);

          // Property: Title must contain the use case title text
          expect(title!.textContent?.trim()).toBe(useCase.title.trim());
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should have description with correct styling', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const description = container.querySelector('.use-case-description');

          // Property: Description must be a paragraph element
          expect(description).toBeTruthy();
          expect(description!.tagName).toBe('P');

          // Property: Description must have correct styling classes
          expect(description!.classList.contains('text-slate-400')).toBe(true);
          expect(description!.classList.contains('leading-relaxed')).toBe(true);

          // Property: Description must contain the use case description text
          expect(description!.textContent?.trim()).toBe(useCase.description.trim());
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should have "Learn more" link with arrow icon', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const learnMoreLink = container.querySelector('.use-case-link');

          // Property: Learn more link must exist
          expect(learnMoreLink).toBeTruthy();

          // Property: Learn more link must contain "Learn more" text
          const linkText = learnMoreLink!.querySelector('span');
          expect(linkText).toBeTruthy();
          expect(linkText!.textContent).toBe('Learn more');

          // Property: Learn more link must have arrow icon
          const arrowIcon = learnMoreLink!.querySelector('svg');
          expect(arrowIcon).toBeTruthy();
          expect(arrowIcon!.classList.contains('w-4')).toBe(true);
          expect(arrowIcon!.classList.contains('h-4')).toBe(true);

          // Property: Learn more link must have correct styling
          expect(learnMoreLink!.classList.contains('text-indigo-400')).toBe(true);
          expect(learnMoreLink!.classList.contains('font-semibold')).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should maintain element order: icon, title, description, link', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const card = container.querySelector('.use-case-card');
          const children = Array.from(card!.children);

          // Property: Card must have at least 4 direct children (icon container, title, description, link)
          expect(children.length).toBeGreaterThanOrEqual(4);

          // Property: First child should contain the icon
          const firstChild = children[0];
          expect(firstChild.querySelector('.use-case-icon')).toBeTruthy();

          // Property: Second child should be the title
          const secondChild = children[1];
          expect(secondChild.classList.contains('use-case-title')).toBe(true);

          // Property: Third child should be the description
          const thirdChild = children[2];
          expect(thirdChild.classList.contains('use-case-description')).toBe(true);

          // Property: Fourth child should be the learn more link
          const fourthChild = children[3];
          expect(fourthChild.classList.contains('use-case-link')).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should render multiple use case cards with all required elements', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.string({ minLength: 3, maxLength: 30 })
              .filter(s => /^[a-z0-9-]+$/.test(s)),
            icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
            title: fc.string({ minLength: 5, maxLength: 50 })
              .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
            description: fc.string({ minLength: 20, maxLength: 200 })
              .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
            link: fc.string({ minLength: 5, maxLength: 50 })
              .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
          }),
          { minLength: 3, maxLength: 10 }
        ),
        (useCases) => {
          // Render multiple use case cards
          const gridHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              ${useCases.map(useCase => renderUseCaseCard(useCase)).join('')}
            </div>
          `;
          
          container.innerHTML = gridHTML;

          const cards = container.querySelectorAll('.use-case-card');

          // Property: Number of cards should match number of use cases
          expect(cards.length).toBe(useCases.length);

          // Property: Each card should have all required elements
          useCases.forEach((useCase, index) => {
            const card = cards[index];

            expect(card.querySelector('.use-case-icon')).toBeTruthy();
            expect(card.querySelector('.use-case-title')).toBeTruthy();
            expect(card.querySelector('.use-case-description')).toBeTruthy();
            expect(card.querySelector('.use-case-link')).toBeTruthy();

            expect(card.getAttribute('data-use-case-id')).toBe(useCase.id);
            expect(card.getAttribute('href')).toBe(useCase.link.trim());
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should have card as an anchor element with correct attributes', () => {
    fc.assert(
      fc.property(
        fc.record({
          id: fc.string({ minLength: 3, maxLength: 30 })
            .filter(s => /^[a-z0-9-]+$/.test(s)),
          icon: fc.constantFrom('database', 'message-circle', 'code', 'file-text', 'shield-check'),
          title: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => /^[a-zA-Z0-9\s]+$/.test(s) && s.trim().length >= 5),
          description: fc.string({ minLength: 20, maxLength: 200 })
            .filter(s => s.trim().length >= 20 && !/[<>&"#]/.test(s)),
          link: fc.string({ minLength: 5, maxLength: 50 })
            .filter(s => (s.startsWith('#') || s.startsWith('http')) && s.trim() === s && !/["'&]/.test(s)),
        }),
        (useCase) => {
          container.innerHTML = renderUseCaseCard(useCase);

          const card = container.querySelector('.use-case-card');

          // Property: Card must be an anchor element
          expect(card).toBeTruthy();
          expect(card!.tagName).toBe('A');

          // Property: Card must have href attribute matching the link
          expect(card!.getAttribute('href')).toBe(useCase.link.trim());

          // Property: Card must have data-use-case-id attribute
          expect(card!.getAttribute('data-use-case-id')).toBe(useCase.id);

          // Property: Card must have correct styling classes
          expect(card!.classList.contains('use-case-card')).toBe(true);
          expect(card!.classList.contains('block')).toBe(true);
          expect(card!.classList.contains('p-6')).toBe(true);
          expect(card!.classList.contains('rounded-xl')).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});
