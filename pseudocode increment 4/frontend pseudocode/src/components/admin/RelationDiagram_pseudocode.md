# RelationDiagram.tsx - Optimized Architecture Pseudocode

## Overview
Komponen untuk menampilkan diagram relasi Parent → Child dalam bentuk SVG yang responsive dan performant. Menggunakan pure functions untuk calculations dan component separation untuk maintainability.

## Core Architecture

### 1. Configuration Interfaces
```typescript
interface DiagramConfig {
  width: number        // Canvas width
  height: number       // Canvas height  
  rowHeight: number    // Height per child row
  padding: number      // Canvas padding
  parentBox: {         // Parent box dimensions
    width: number
    height: number
  }
}

interface DiagramLayout {
  config: DiagramConfig
  parentPos: { x: number; y: number }
  childrenPos: Array<{
    x: number
    y: number
    child: ChildLite | null
  }>
}
```

### 2. Pure Calculation Functions

#### Layout Calculator
```
FUNCTION calculateDiagramLayout(childCount):
  // Dynamic sizing based on content
  config = {
    width: MAX(400, childCount * 20 + 300),
    height: MAX(120, childCount * 28 + 40), 
    rowHeight: 28,
    padding: 20,
    parentBox: { width: 80, height: 32 }
  }
  
  // Parent box positioning (left side)
  parentPos = {
    x: config.padding,
    y: (config.height / 2) - (config.parentBox.height / 2)
  }
  
  // Children positioning (right side, vertically distributed)
  childrenStartY = config.padding
  childrenX = config.width - 140
  
  childrenPos = []
  FOR i = 0 TO childCount - 1:
    ADD {
      x: childrenX,
      y: childrenStartY + (i * config.rowHeight) + (config.rowHeight / 2),
      child: null  // Placeholder, actual child assigned later
    } TO childrenPos
  END
  
  RETURN {
    config,
    parentPos, 
    childrenPos
  }
END
```

### 3. SVG Component Architecture

#### Connection Path Component
```
COMPONENT ConnectionPath({ from, to }):
  // Smooth curved connection using bezier curve
  midX = (from.x + to.x) / 2
  pathData = `M ${from.x} ${from.y} C ${midX} ${from.y} ${midX} ${to.y} ${to.x - 5} ${to.y}`
  
  RENDER:
    <path 
      d={pathData}
      stroke="var(--gray-200)"
      strokeWidth="1.5"
      fill="none"
    />
END
```

#### Parent Box Component  
```
COMPONENT ParentBox({ parent, position, config }):
  { x, y } = position
  { width, height } = config.parentBox
  
  RENDER:
    <g>
      // Main parent box
      <rect
        x={x} y={y}
        width={width} height={height}
        rx="8"
        fill="var(--purple-muda)"
        stroke="var(--purple-primary)"
        strokeWidth="1.2"
      />
      
      // Parent ID label
      <text
        x={x + width/2} y={y + 12}
        textAnchor="middle"
        fontSize="10"
        fill="#4C1D95"
        fontFamily="Inter, sans-serif"
        fontWeight="600"
      >
        {parent.parent_id}
      </text>
      
      // Children count label
      <text
        x={x + width/2} y={y + 25}
        textAnchor="middle"
        fontSize="8"
        fill="#6D28D9"
        fontFamily="Inter, sans-serif"
      >
        {parent.children.length} children
      </text>
    </g>
END
```

#### Child Node Component
```
COMPONENT ChildNode({ child, position }):
  { x, y } = position
  
  RENDER:
    <g>
      // Child indicator circle
      <circle
        cx={x} cy={y}
        r="4"
        fill="var(--purple-primary)"
      />
      
      // Child info text
      <text x={x + 12} y={y + 1} fontSize="10" fontFamily="Inter, sans-serif">
        // Child ID (bold)
        <tspan fill="#374151" fontWeight="600">
          {child.id}
        </tspan>
        
        // Child title (normal)
        <tspan fill="#6B7280" dx="6">
          {child.title}
        </tspan>
      </text>
    </g>
END
```

### 4. Main Diagram Component

#### Diagram Content
```
COMPONENT DiagramContent({ parent }):
  // Memoized layout calculation untuk performance
  layout = MEMO calculateDiagramLayout(parent.children.length) DEPENDS ON [parent.children.length]
  
  // Calculate parent center point untuk connection lines
  parentCenter = {
    x: layout.parentPos.x + layout.config.parentBox.width,
    y: layout.parentPos.y + (layout.config.parentBox.height / 2)
  }
  
  RENDER:
    <div className="relation-svg-wrap">
      <svg
        viewBox={`0 0 ${layout.config.width} ${layout.config.height}`}
        preserveAspectRatio="xMidYMid meet"
        style={{
          minWidth: `${layout.config.width}px`,
          width: '100%',
          height: `${layout.config.height}px`
        }}
      >
        // Draw connection lines first (behind other elements)
        FOR EACH child, index IN parent.children:
          <ConnectionPath
            key={child.id}
            from={parentCenter}
            to={{
              x: layout.childrenPos[index].x,
              y: layout.childrenPos[index].y
            }}
          />
        END
        
        // Draw parent box
        <ParentBox
          parent={parent}
          position={layout.parentPos}
          config={layout.config}
        />
        
        // Draw child nodes
        FOR EACH child, index IN parent.children:
          <ChildNode
            key={child.id}
            child={child}
            position={layout.childrenPos[index]}
          />
        END
      </svg>
    </div>
END
```

#### Main Component with Toggle
```
COMPONENT RelationDiagram({ parent }):
  STATE isOpen = false
  
  IF NOT parent:
    RETURN null
  END
  
  FUNCTION toggleOpen():
    SET isOpen = !isOpen
  END
  
  RENDER:
    <>
      // Toggle button
      <button
        className={`relation-toggle ${isOpen ? 'open' : ''}`}
        onClick={toggleOpen}
      >
        <LayerIcon />
        <Text>Lihat relasi Parent → Child</Text>
        <ChevronIcon className={`chev ${isOpen ? 'rotated' : ''}`} />
      </button>
      
      // Collapsible diagram content
      <div className={`relation-body ${isOpen ? 'open' : ''}`}>
        <DiagramContent parent={parent} />
      </div>
    </>
END
```

## Performance Optimizations

### 1. Memoized Calculations
```
// Layout calculation hanya dilakukan ketika childCount berubah
layout = useMemo(() => calculateDiagramLayout(childCount), [childCount])
```

### 2. Pure Functions
- `calculateDiagramLayout`: Pure function, predictable output
- No side effects, easy testing
- Consistent behavior untuk same inputs

### 3. SVG Optimization
- `viewBox` dan `preserveAspectRatio` untuk responsive design
- Minimal DOM elements dengan efficient grouping
- CSS variables untuk consistent theming

### 4. Component Separation
- Separated concerns: layout calculation vs rendering
- Reusable components: ConnectionPath, ParentBox, ChildNode
- Easy maintenance dan testing

## Responsive Design Strategy

### 1. Dynamic Sizing
```
width = MAX(400, childCount * 20 + 300)   // Scales with content
height = MAX(120, childCount * 28 + 40)   // Minimum height guaranteed
```

### 2. SVG Responsiveness  
```
viewBox="0 0 {width} {height}"           // Defines coordinate system
preserveAspectRatio="xMidYMid meet"      // Maintains aspect ratio
style={{ width: '100%' }}               // Fills container
```

### 3. Text Scaling
- Font sizes dalam pixels untuk consistency
- Text positioning relative to SVG coordinates
- Proper text anchoring untuk alignment

## Data Flow Architecture

```
parent (ParentNode)
  ↓ calculateDiagramLayout (pure function)
  ↓ layout configuration
  ↓ SVG rendering dengan components
  ↓ User interaction (toggle) → state update → re-render
```

## Error Boundaries & Edge Cases

### 1. Empty Parent
```
IF NOT parent:
  RETURN null  // Component tidak render
END
```

### 2. No Children
```
IF parent.children.length === 0:
  // Layout tetap calculated, tapi tidak ada child nodes
  RENDER parent box only
END
```

### 3. Large Dataset
- Dynamic sizing handles up to reasonable limits
- Performance tetap optimal karena memoization
- SVG efficiently handles many elements

### 4. Responsive Breakpoints
- SVG scales naturally dengan container
- Text remains readable pada different sizes
- Layout proportions maintained

## Advantages of Optimized Architecture

### 1. Performance Benefits
- **Memoized calculations**: Layout hanya calculated saat childCount berubah
- **Pure functions**: Predictable, testable, cacheable
- **Component separation**: Efficient re-rendering

### 2. Maintainability  
- **Clear separation**: Layout logic vs rendering logic
- **Reusable components**: ParentBox, ChildNode dapat digunakan elsewhere
- **Self-documenting**: Function names explain their purpose

### 3. Scalability
- **Dynamic sizing**: Handles variable data sizes
- **Responsive design**: Works pada different screen sizes  
- **Performance scaling**: Linear performance dengan data size

### 4. Code Quality
- **Type safety**: Strong TypeScript interfaces
- **No magic numbers**: All dimensions dalam config object
- **Consistent styling**: CSS variables untuk theming

## Configuration Flexibility

### 1. Easy Customization
```typescript
// Semua styling parameters dalam config object
interface DiagramConfig {
  width: number        // Easily adjustable
  height: number       // Responsive calculation
  rowHeight: number    // Child spacing
  padding: number      // Canvas margins
  parentBox: { ... }   // Parent dimensions
}
```

### 2. Theme Integration
- CSS variables untuk colors: `var(--purple-primary)`
- Consistent dengan design system
- Easy dark/light mode switching

### 3. Extensibility
- Additional node types dapat easily added
- New connection styles dapat implemented
- Animation dapat added without breaking existing code