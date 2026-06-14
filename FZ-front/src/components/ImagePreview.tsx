import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useState } from 'react'

type ImagePreviewProps = {
  images: string[]
  initialIndex: number
  alt: string
  onClose: () => void
}

export function ImagePreview({ images, initialIndex, alt, onClose }: ImagePreviewProps) {
  const [activeIndex, setActiveIndex] = useState(() => clampIndex(initialIndex, images.length))
  const imageCount = images.length
  const safeActiveIndex = clampIndex(activeIndex, imageCount)

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowLeft' && imageCount > 1) {
        setActiveIndex((current) => (current - 1 + imageCount) % imageCount)
      }
      if (event.key === 'ArrowRight' && imageCount > 1) {
        setActiveIndex((current) => (current + 1) % imageCount)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [imageCount, onClose])

  if (imageCount === 0) return null

  return (
    <div className="image-preview-backdrop" role="dialog" aria-modal="true" aria-label="图片预览">
      <div className="image-preview-topbar">
        <span>
          {safeActiveIndex + 1}/{imageCount}
        </span>
        <button type="button" aria-label="关闭图片预览" onClick={onClose}>
          <X size={25} />
        </button>
      </div>
      <div className="image-preview-stage">
        {imageCount > 1 ? (
          <button
            className="image-preview-nav image-preview-prev"
            type="button"
            aria-label="上一张图片"
            onClick={() => setActiveIndex((current) => (current - 1 + imageCount) % imageCount)}
          >
            <ChevronLeft size={30} />
          </button>
        ) : null}
        <img src={images[safeActiveIndex]} alt={alt} />
        {imageCount > 1 ? (
          <button
            className="image-preview-nav image-preview-next"
            type="button"
            aria-label="下一张图片"
            onClick={() => setActiveIndex((current) => (current + 1) % imageCount)}
          >
            <ChevronRight size={30} />
          </button>
        ) : null}
      </div>
      {imageCount > 1 ? (
        <div className="image-preview-dots" aria-label="图片预览切换">
          {images.map((image, index) => (
            <button
              className={safeActiveIndex === index ? 'is-active' : ''}
              key={`${image}-${index}`}
              type="button"
              aria-label={`查看第${index + 1}张图片`}
              onClick={() => setActiveIndex(index)}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function clampIndex(index: number, length: number) {
  if (length <= 0) return 0
  return Math.min(Math.max(index, 0), length - 1)
}
